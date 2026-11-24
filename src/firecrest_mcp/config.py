"""Checks of tool arguments against the config file, .firecrest-mcp.toml."""

import os
import tomllib
from pathlib import Path, PurePosixPath
from typing import Annotated, Self
from urllib.parse import urlsplit

from fastmcp.exceptions import ToolError
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    ValidationError,
    model_validator,
)

from firecrest_mcp.auth import token_path

# Resolved against the working directory of the server process.
CONFIG_PATH = Path(".firecrest-mcp.toml")


def _protected_local_paths() -> list[Path]:
    """Return the local paths that no tool may use, resolved."""
    # A tool that writes to these files could change the server's or the agent's
    # configuration or run code, and one that reads the token file could copy the
    # token. Relative paths are relative to the working directory.
    paths = [
        CONFIG_PATH,
        Path(".mcp.json"),
        Path(".claude"),
        Path(".git"),
        token_path(),
    ]
    return [path.resolve() for path in paths]


# Directories that a cluster has under two names, by cluster. Config entries and
# checked paths are rewritten to the second name before they are compared, so
# either name in the config allows both.
PATH_ALIASES = {"lumi": {"/project": "/projappl"}}


def _config_error(message: str) -> ToolError:
    return ToolError(f"Config file {CONFIG_PATH.absolute()}: {message}")


def _not_allowed(label: str, value: str, key: str) -> ToolError:
    return ToolError(f"{label} {value!r} is not in {key} in {CONFIG_PATH.absolute()}.")


def _require_default(option: str, value: str | None) -> str:
    if value is None:
        raise ToolError(
            f"No {option} given and default_{option} is not set in"
            f" {CONFIG_PATH.absolute()}."
        )
    return value


def _check_local_syntax(path: str) -> str:
    # Path("") is the working directory, so an empty entry would allow all of it.
    if path == "":
        raise ValueError("must not be an empty string")
    return path


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
    # FirecREST releases up to 2.6.2 put the path of a large download into a transfer
    # job script without quotes, and that of a large upload in double quotes. There,
    # these characters could end the path and run the rest as commands.
    if any(char in ' "\\;&|<>()$`' for char in path):
        raise ValueError(
            f'{path!r} must not contain spaces or any of the characters "\\;&|<>()$`'
        )
    return path


def cluster_name() -> str:
    """Return the name of the cluster's table in the config file: the first label of
    the FIRECREST_URL hostname other than "api", e.g. "roihu" for
    https://api.roihu.csc.fi/v1."""
    url = os.getenv("FIRECREST_URL", "")
    hostname = urlsplit(url).hostname or ""
    # Drop the empty labels of a missing hostname or of one like "a..b".
    labels = []
    for label in hostname.split("."):
        if label:
            labels.append(label)
    if labels and labels[0] == "api":
        labels.pop(0)
    if not labels:
        raise ToolError(f"Cannot derive a cluster name from FIRECREST_URL {url!r}.")
    return labels[0]


def _real_entry(entry: str) -> Path:
    """Return a local_paths entry as an absolute path with "~" expanded.

    Raises a ToolError if the entry's path contains a symlink, because changing
    the link would change which directory local_paths allows.
    """
    # The working directory is resolved first, so that only a link in the entry itself
    # makes the two paths differ, not one above the working directory.
    absolute = Path(os.path.normpath(Path.cwd().resolve() / Path(entry).expanduser()))
    real = absolute.resolve()
    if absolute != real:
        raise _config_error(
            f"local_paths entry {entry!r} contains a symlink. List its real path"
            f" {str(real)!r} instead."
        )
    return real


def _protected_stats() -> list[os.stat_result]:
    """Return the stat results of the protected local paths that exist."""
    stats = []
    for path in _protected_local_paths():
        if path.exists():
            stats.append(path.stat())
    return stats


def _is_protected(real: Path) -> bool:
    """Return whether a real path is a protected path or lies in one."""
    if any(real.is_relative_to(p) for p in _protected_local_paths()):
        return True
    # Comparing device and inode numbers also finds a hard link to a protected file,
    # and another spelling of a protected path on a file system that ignores case.
    protected_stats = _protected_stats()
    for part in [real, *real.parents]:
        if part.exists():
            part_stat = part.stat()
            if any(os.path.samestat(part_stat, s) for s in protected_stats):
                return True
    return False


def _normalized_path(path: str, aliases: dict[str, str]) -> PurePosixPath:
    """Return a remote path with an aliased directory replaced by its main name.
    PurePosixPath drops "." components and repeated slashes, and is_relative_to
    compares whole components, so /projectx is not under /project."""
    normalized = PurePosixPath(path)
    for alias, target in aliases.items():
        if normalized.is_relative_to(alias):
            return PurePosixPath(target, normalized.relative_to(alias))
    return normalized


class Config(BaseModel):
    """What the tools may do on this server: the top-level local_paths and the keys of
    this server's cluster table. The table applies to all of the cluster's systems
    (e.g. Roihu's cpu and gpu), which share Slurm and file systems. A missing key
    allows nothing."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    local_paths: list[Annotated[str, AfterValidator(_check_local_syntax)]]
    remote_paths: list[Annotated[str, AfterValidator(_check_remote_syntax)]] = []
    accounts: list[str] = []
    default_account: str | None = None
    partitions: list[str] = []
    default_partition: str | None = None
    reservations: list[str] = []
    groups: list[str] = []

    @model_validator(mode="after")
    def _check_defaults(self) -> Self:
        for option, default, allowed in [
            ("account", self.default_account, self.accounts),
            ("partition", self.default_partition, self.partitions),
        ]:
            if default is not None and default not in allowed:
                raise ValueError(f"default_{option} {default!r} is not in {option}s")
        return self

    def checked_local_path(self, path: str) -> Path:
        """Return the real path of a local path, with "~" expanded and symlinks
        resolved, if it is one of the local_paths or lies below one.

        Raises a ToolError for a path outside local_paths and for a protected path. A
        relative entry or path is relative to the working directory. Tools pass the
        returned path on, because the given one may name another file, such as
        "~/x" for open(), which doesn't expand "~".
        """
        allowed = [_real_entry(entry) for entry in self.local_paths]
        real = Path(path).expanduser().resolve()
        if _is_protected(real):
            raise ToolError(f"Local path {path!r} is protected.")
        if not any(real.is_relative_to(d) for d in allowed):
            raise _not_allowed("Local path", path, "local_paths")
        return real

    def check_remote_paths(self, *paths: str | None) -> None:
        """Raise a ToolError unless every given remote path is one of the
        remote_paths or lies below one. ``None`` values are skipped so that optional
        parameters can be passed directly."""
        aliases = PATH_ALIASES.get(cluster_name(), {})
        allowed = [_normalized_path(entry, aliases) for entry in self.remote_paths]
        for path in paths:
            if path is None:
                continue
            try:
                _check_remote_syntax(path)
            except ValueError as e:
                raise ToolError(f"Remote path {e}.") from None
            # is_relative_to compares whole components, so /scratch/project_10 is
            # not under /scratch/project_1.
            normalized = _normalized_path(path, aliases)
            if not any(normalized.is_relative_to(entry) for entry in allowed):
                raise _not_allowed("Remote path", path, "remote_paths")

    def checked_account(self, account: str | None) -> str:
        """Return the account to use: the given one if allowed, or default_account."""
        if account is None:
            return _require_default("account", self.default_account)
        if account not in self.accounts:
            raise _not_allowed("Account", account, "accounts")
        return account

    def checked_transfer(self, account: str | None, *paths: str) -> str:
        """Check the remote paths of a tool that may run a transfer job, and return
        the account to use for the job."""
        self.check_remote_paths(*paths)
        return self.checked_account(account)

    def check_group(self, group: str) -> None:
        if group not in self.groups:
            raise _not_allowed("Group", group, "groups")

    def checked_job_options(
        self,
        account: str | None,
        partition: str | None,
        reservation: str | None,
    ) -> tuple[str, str]:
        """Check a job's arguments against the config, and return the account and
        partition to submit it with: the given ones, or default_account and
        default_partition. They are always passed, so they override the script's
        #SBATCH lines, which are not checked.
        """
        # Partitions and reservations may be comma-separated lists. An empty
        # argument is checked too, as FirecREST or Slurm would replace it with
        # their own default.
        for option, argument, allowed in [
            ("partition", partition, self.partitions),
            ("reservation", reservation, self.reservations),
        ]:
            if argument is None:
                continue
            for value in argument.split(","):
                if value not in allowed:
                    raise _not_allowed(option.capitalize(), value, f"{option}s")

        if partition is None:
            partition = _require_default("partition", self.default_partition)
        return self.checked_account(account), partition


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


def load_config() -> Config:
    """Return the config for this server. Other clusters' tables are not read."""
    data = _read_config()
    name = cluster_name()
    if name not in data:
        raise _config_error(f"there is no [{name}] table, so nothing is allowed.")
    # local_paths is a top-level key. A copy in the cluster's table would be
    # overwritten below and ignored without an error, so it is refused.
    if "local_paths" in data[name]:
        raise _config_error(f"local_paths must be a top-level key, not in [{name}].")
    fields = dict(data[name])
    # Without local_paths, no local path is allowed.
    fields["local_paths"] = data.get("local_paths", [])
    try:
        return Config.model_validate(fields)
    except ValidationError as e:
        problems = []
        for err in e.errors():
            # loc is the path to the bad value, e.g. ("remote_paths", 0), or empty for
            # a check of the whole table. Keys other than local_paths are named as in
            # the file, e.g. lumi.remote_paths.0.
            parts = []
            if not err["loc"] or err["loc"][0] != "local_paths":
                parts.append(name)
            for part in err["loc"]:
                parts.append(str(part))
            location = ".".join(parts)
            problems.append(f"{location}: {err['msg']}")
        raise _config_error("; ".join(problems)) from None
