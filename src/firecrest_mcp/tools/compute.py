"""Tools for Slurm jobs: submitting, querying, cancelling and attaching to them."""

import re
import shlex
from typing import Annotated

import cachetools.func
from fastmcp.exceptions import ToolError
from fastmcp.tools import tool
from firecrest import UnexpectedStatusException
from firecrest.v2 import Firecrest

from firecrest_mcp.config import load_config
from firecrest_mcp.tools.params import JobId, SystemName

# Seconds that _user_name keeps the user's name. The name changes only if the token
# file gets another account's token, such as a robot account's. own_jobs then uses
# the old name for this long.
USER_NAME_TTL = 3 * 60
# Seconds that job_info keeps a result. submit and cancel_job clear it, so only
# changes made elsewhere, such as a job that finishes, can show late.
JOB_INFO_TTL = 20
# Seconds that job_metadata keeps a result. A job's metadata doesn't change.
JOB_METADATA_TTL = 60


@cachetools.func.ttl_cache(maxsize=2, ttl=USER_NAME_TTL)
def _user_name(client: Firecrest, system_name: str) -> str:
    """Return the user's name on a system."""
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


def check_own_job(client: Firecrest, system_name: str, jobid: str) -> None:
    """Raise a ToolError unless the job belongs to the user."""
    jobs = client.job_info(system_name, jobid=jobid)
    own_jobs(client, system_name, jobs, jobid)


class FirecrestComputeToolsMixin:
    client: Firecrest

    @tool()
    def submit(
        self,
        system_name: SystemName,
        working_dir: Annotated[str, "the working directory of the job"],
        script_str: Annotated[str | None, "the job script"] = None,
        script_local_path: Annotated[
            str | None,
            "the local path of the job script, absolute or relative to the server's"
            " working directory",
        ] = None,
        script_remote_path: Annotated[
            str | None, "path to the job script on the system"
        ] = None,
        env_vars: Annotated[
            dict[str, str] | None, "environment variables to set for the job"
        ] = None,
        account: Annotated[str | None, "the account to bill"] = None,
        partition: Annotated[str | None, "the partition to run in"] = None,
        reservation: Annotated[str | None, "the reservation to run in"] = None,
    ) -> dict:
        """Submit a job. Exactly one of script_str, script_local_path or
        script_remote_path must be given. The account and partition, or their
        defaults from the config, override the script's #SBATCH lines.
        """
        scripts = [script_str, script_local_path, script_remote_path]
        if sum(script is not None for script in scripts) != 1:
            raise ToolError(
                "Exactly one of script_str, script_local_path or script_remote_path"
                " must be given."
            )
        config = load_config()
        config.check_remote_paths(working_dir, script_remote_path)
        if script_local_path is not None:
            script_local_path = str(config.checked_local_path(script_local_path))
        account, partition = config.checked_job_options(account, partition, reservation)
        result = self.client.submit(
            system_name,
            working_dir=working_dir,
            script_str=script_str,
            script_local_path=script_local_path,
            script_remote_path=script_remote_path,
            env_vars=env_vars,
            account=account,
            partition=partition,
            reservation=reservation,
        )
        # The cached job lists don't have the new job.
        FirecrestComputeToolsMixin.job_info.cache_clear()
        return result

    # The description replaces the docstring, so that it can name the cache time.
    @tool(
        description="Get information about your own Slurm jobs. Without a jobid,"
        " list all of them that match the filters. Other users' jobs are not"
        f" available. The result may be up to {JOB_INFO_TTL} seconds old, but jobs"
        " that you submit or cancel show at once."
    )
    @cachetools.func.ttl_cache(maxsize=10, ttl=JOB_INFO_TTL)
    def job_info(
        self,
        system_name: SystemName,
        jobid: JobId | None = None,
        account: Annotated[
            str | None, "show only the jobs of this account; ignored with a jobid"
        ] = None,
        name: Annotated[
            str | None, "show only the jobs with this name; ignored with a jobid"
        ] = None,
        time_window: Annotated[
            str | None,
            "how far back to look for finished (completed, failed, cancelled…) jobs:"
            " 1h, 8h, 24h, 3d or 7d. Pending and running jobs are always returned."
            " Ignored with a jobid.",
        ] = None,
    ) -> list:
        jobs = self.client.job_info(
            system_name,
            jobid=jobid,
            allusers=False,
            account=account,
            name=name,
            time_window=time_window,
        )
        return own_jobs(self.client, system_name, jobs, jobid)

    @tool()
    @cachetools.func.ttl_cache(maxsize=10, ttl=JOB_METADATA_TTL)
    def job_metadata(
        self,
        system_name: SystemName,
        jobid: JobId,
    ) -> list[dict]:
        """Get the metadata of one of your jobs."""
        check_own_job(self.client, system_name, jobid)
        return self.client.job_metadata(system_name, jobid=jobid)

    @tool()
    def cancel_job(
        self,
        system_name: SystemName,
        jobid: JobId,
    ) -> dict:
        """Cancel one of your jobs."""
        check_own_job(self.client, system_name, jobid)
        result = self.client.cancel_job(system_name, jobid=jobid)
        # The cached job lists show the job in its state before the cancel.
        FirecrestComputeToolsMixin.job_info.cache_clear()
        return result

    @tool()
    def attach_to_job(
        self,
        system_name: SystemName,
        jobid: JobId,
        command: Annotated[str, "the command to run, which bash runs in the job"],
        output_path: Annotated[
            str,
            "the file on the system that gets the command's output and errors. It is"
            " overwritten.",
        ],
    ) -> dict:
        """Run a command inside one of your running jobs, with its output written to
        output_path. The command gets srun's default resources, such as one CPU, not
        the job's. FirecREST kills it after the time limit that the systems tool
        shows as ssh.timeout.commandExecution.
        """
        load_config().check_remote_paths(output_path)
        check_own_job(self.client, system_name, jobid)
        # FirecREST runs "srun ... <command>" in a login node shell, which would run
        # anything after a ";" itself. bash -c keeps the whole command in the job.
        # srun forwards its stdin to the job, so a command that reads stdin gets
        # /dev/null and not the SSH session's stdin.
        shell_line = (
            f"bash -c {shlex.quote(command)} > {shlex.quote(output_path)} 2>&1"
            " < /dev/null"
        )
        try:
            self.client.attach_to_job(system_name, jobid=jobid, command=shell_line)
        except UnexpectedStatusException as error:
            return attach_error_result(error, output_path)
        return {"output_path": output_path, "status": "finished", "exit_status": 0}


def attach_error_result(error: UnexpectedStatusException, output_path: str) -> dict:
    """Return the result of an attached command that timed out or exited with an
    error, whose output is in output_path. Re-raise any other error."""
    response = error.responses[-1]
    if response.status_code == 504:
        return {
            "output_path": output_path,
            "status": "killed",
            "note": "The command ran longer than FirecREST's time limit and was"
            " killed. Submit longer work as a job.",
        }
    # FirecREST reports a nonzero exit as a 500 error with "exit_status:<N>" in its
    # message.
    if response.status_code == 500:
        try:
            message = response.json().get("message", "")
        except ValueError:
            message = ""
        match = re.search(r"exit_status:(\d+)", message)
        if match:
            return {
                "output_path": output_path,
                "status": "finished",
                "exit_status": int(match.group(1)),
            }
    raise error
