"""Checks of tool arguments against the config file, .firecrest-mcp.toml."""

import os
import posixpath
import tomllib
from pathlib import Path, PurePosixPath
from typing import Annotated, Self
from urllib.parse import urlsplit

import cachetools.func
from fastmcp.exceptions import ToolError
from firecrest.v2 import Firecrest
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    ValidationError,
    model_validator,
)

from firecrest_mcp import sbatch
from firecrest_mcp.auth import token_path

# Resolved against the working directory of the server process.
CONFIG_PATH = Path(".firecrest-mcp.toml")

# Local paths that are never allowed, because writing them could change the server's
# or the agent's own configuration or run code: relative to the working directory.
PROTECTED_LOCAL_PATHS = (CONFIG_PATH, Path(".mcp.json"), Path(".claude"), Path(".git"))

# Environment variables that could set job options outside the checks.
PROTECTED_ENV_PREFIXES = ("SBATCH_", "SLURM_")

# Directories that a cluster has under two names, by cluster. Config entries and
# checked paths are rewritten to the second name before they are compared, so
# either name in the config allows both.
PATH_ALIASES = {"lumi": {"/project": "/projappl"}}


def _config_error(message: str) -> ToolError:
    return ToolError(f"Config file {CONFIG_PATH.absolute()}: {message}")


def _not_allowed(what: str, value: str, key: str) -> ToolError:
    return ToolError(f"{what} {value!r} is not in {key} in {CONFIG_PATH.absolute()}.")


def _default(option: str, value: str | None) -> str:
    if value is None:
        raise ToolError(
            f"No {option} given and default_{option} is not set in"
            f" {CONFIG_PATH.absolute()}."
        )
    return value


def _check_remote_syntax(path: str) -> str:
    if not path.startswith("/"):
        raise ValueError(f"{path!r} is not absolute")
    # Collapsing ".." without knowing the remote symlinks could turn a path that
    # escapes the allowed tree into one that looks allowed, so refuse it outright.
    if ".." in path.split("/"):
        raise ValueError(f"{path!r} must not contain '..'")
    # FirecREST puts paths into shell commands in single quotes without escaping
    # them, so a quote would end the path and run the rest as commands.
    if "'" in path or any(not char.isprintable() for char in path):
        raise ValueError(f"{path!r} must not contain quotes or control characters")
    return path


def cluster_name() -> str:
    """Return the name of the cluster's table in the config file: the first label of
    the FIRECREST_URL hostname other than "api", e.g. "roihu" for
    https://api.roihu.csc.fi/v1."""
    url = os.getenv("FIRECREST_URL", "")
    labels = [label for label in (urlsplit(url).hostname or "").split(".") if label]
    if labels and labels[0] == "api":
        labels.pop(0)
    if not labels:
        raise ToolError(f"Cannot derive a cluster name from FIRECREST_URL {url!r}.")
    return labels[0]


def _canonical(path: str, aliases: dict[str, str]) -> PurePosixPath:
    """Return a remote path with an aliased directory replaced by its main name.
    PurePosixPath drops "." components and repeated slashes, and is_relative_to
    compares whole components, so /projectx is not under /project."""
    canonical = PurePosixPath(path)
    for alias, target in aliases.items():
        if canonical.is_relative_to(alias):
            return PurePosixPath(target, canonical.relative_to(alias))
    return canonical


class ClusterPolicy(BaseModel):
    """What the tools may do on one cluster, from its table. It applies to all of the
    cluster's systems (e.g. Roihu's cpu and gpu), which share Slurm and file
    systems. A missing key allows nothing."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    remote_paths: list[Annotated[str, AfterValidator(_check_remote_syntax)]] = []
    accounts: list[str] = []
    default_account: str | None = None
    partitions: list[str] = []
    default_partition: str | None = None
    reservations: list[str] = []
    groups: list[str] = []

    @model_validator(mode="after")
    def _check_defaults(self) -> Self:
        for option in ("account", "partition"):
            default = getattr(self, f"default_{option}")
            if default not in (None, *getattr(self, f"{option}s")):
                raise ValueError(f"default_{option} {default!r} is not in {option}s")
        return self

    def check_remote_paths(self, *paths: str | None) -> None:
        """Raise a ToolError unless every given remote path is one of the
        remote_paths or lies below one. ``None`` values are skipped so that optional
        parameters can be passed directly."""
        aliases = PATH_ALIASES.get(cluster_name(), {})
        allowed = [_canonical(entry, aliases) for entry in self.remote_paths]
        for path in paths:
            if path is None:
                continue
            try:
                _check_remote_syntax(path)
            except ValueError as e:
                raise ToolError(f"Remote path {e}.") from None
            # is_relative_to compares whole components, so /scratch/project_10 is
            # not under /scratch/project_1.
            canonical = _canonical(path, aliases)
            if not any(canonical.is_relative_to(entry) for entry in allowed):
                raise _not_allowed("Remote path", path, "remote_paths")

    def account(self, account: str | None) -> str:
        """Return the account to use: the given one if allowed, or default_account."""
        if account is None:
            return _default("account", self.default_account)
        if account not in self.accounts:
            raise _not_allowed("Account", account, "accounts")
        return account

    def check_transfer(self, account: str | None, *paths: str) -> str:
        """Check the remote paths of a tool that may run a transfer job, and return
        the account to use for the job."""
        self.check_remote_paths(*paths)
        return self.account(account)

    def check_group(self, group: str) -> None:
        if group not in self.groups:
            raise _not_allowed("Group", group, "groups")

    def job_options(
        self,
        script: str,
        working_dir: str | None,
        env_vars: dict[str, str] | None,
        account: str | None,
        partition: str | None,
        reservation: str | None,
    ) -> tuple[str | None, str | None]:
        """Check a job's arguments and #SBATCH lines against the policy, and return
        the account and partition to submit it with.

        An argument overrides the script, as with sbatch. If only the script sets
        the account, None is returned so that the script's account is used. If
        neither sets it, default_account is returned. The partition works the same
        way.
        """
        try:
            directives = sbatch.parse_directives(script)
        except ValueError as e:
            raise ToolError(f"Job script: {e}") from e

        for key in env_vars or {}:
            if key.upper().startswith(PROTECTED_ENV_PREFIXES):
                raise ToolError(
                    f"Environment variable {key!r} could change job options, so it is"
                    " not allowed."
                )

        # Partitions and reservations may be comma-separated lists. An empty
        # argument is checked too, as FirecREST or Slurm would replace it with
        # their own default.
        for option, argument, allowed in [
            ("account", account, self.accounts),
            ("partition", partition, self.partitions),
            ("reservation", reservation, self.reservations),
        ]:
            given = directives.get(option, []) + (
                [] if argument is None else [argument]
            )
            for value in (v for values in given for v in values.split(",")):
                if value not in allowed:
                    raise _not_allowed(option.capitalize(), value, f"{option}s")

        # sbatch resolves relative paths against the job's working directory, which
        # the last --chdir sets.
        base = working_dir
        for option in ("chdir", "output", "error", "input"):
            for value in directives.get(option, []):
                if not value.startswith("/"):
                    if not base:
                        raise ToolError(
                            f"Relative #SBATCH --{option} {value!r} needs a working"
                            " directory."
                        )
                    value = posixpath.join(base, value)
                self.check_remote_paths(value)
                if option == "chdir":
                    base = value

        if account is None and "account" not in directives:
            account = _default("account", self.default_account)
        if partition is None and "partition" not in directives:
            partition = _default("partition", self.default_partition)
        return account, partition


def _read_config() -> dict:
    """Read the config file. It is read on every call, so edits take effect without
    a restart."""
    try:
        with CONFIG_PATH.open("rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        raise _config_error("does not exist, so nothing is allowed.") from None
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise _config_error(str(e)) from e
    # Every other top-level key is a cluster's table, so a misspelled key shows up
    # as a value that is not a table.
    for key, value in data.items():
        if key != "local_paths" and not isinstance(value, dict):
            raise _config_error(f"{key} must be a table.")
    return data


def load_cluster() -> ClusterPolicy:
    """Return the policy for this server's cluster. Other clusters' tables are not
    read."""
    data = _read_config()
    name = cluster_name()
    if name not in data:
        raise _config_error(f"there is no [{name}] table, so nothing is allowed.")
    try:
        return ClusterPolicy.model_validate(data[name])
    except ValidationError as e:
        raise _config_error(
            "; ".join(
                f"{'.'.join(map(str, (name, *err['loc'])))}: {err['msg']}"
                for err in e.errors()
            )
        ) from None


def check_local_paths(*paths: str | os.PathLike | None) -> None:
    """Raise a ToolError unless every given local path is one of the top-level
    local_paths or lies below one. Relative entries and paths are relative to the
    working directory, and both are resolved, following symlinks, before they are
    compared. ``None`` values are skipped."""
    entries = _read_config().get("local_paths", [])
    if not isinstance(entries, list) or not all(isinstance(e, str) for e in entries):
        raise _config_error("local_paths must be a list of strings.")
    allowed = [Path(entry).expanduser().resolve() for entry in entries]
    protected = [p.resolve() for p in PROTECTED_LOCAL_PATHS]
    protected.append(token_path().resolve())
    for path in paths:
        if path is None:
            continue
        resolved = Path(path).expanduser().resolve()
        if any(resolved.is_relative_to(p) for p in protected):
            raise ToolError(f"Local path {str(path)!r} is protected.")
        if not any(resolved.is_relative_to(d) for d in allowed):
            raise _not_allowed("Local path", str(path), "local_paths")


@cachetools.func.ttl_cache(maxsize=2, ttl=60 * 3)
def _user_name(client: Firecrest, system_name: str) -> str:
    """Return the user's name on a system. It changes only if the token file is
    replaced with another user's token, so it is cached for a few minutes."""
    return client.userinfo(system_name)["user"]["name"]


def own_jobs(
    client: Firecrest, system_name: str, jobs: list, jobid: str | None = None
) -> list:
    """Return the jobs that belong to the user. FirecREST returns other users' jobs
    when they are asked for by ID, so asking for another user's job is an error."""
    user = _user_name(client, system_name)
    own = [job for job in jobs if job.get("user") == user]
    if jobid is not None and not own:
        raise ToolError(f"Job {jobid} is not one of your jobs.")
    return own
