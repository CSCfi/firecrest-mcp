from typing import Annotated

from fastmcp.tools import tool
import cachetools.func

class FirecrestComputeToolsMixin:
    @tool()
    def submit(
        self,
        system_name: Annotated[str, "the system name where the filesystem belongs to"],
        working_dir: Annotated[str | None, "the working directory of the job"],
        script_str: Annotated[str | None, "the job script"] = None,
        script_local_path: Annotated[str | None, "path to the job script"] = None,
        script_remote_path: Annotated[
            str | None, "path to the job script on the remote filesystem"
        ] = None,
        env_vars: Annotated[
            dict[str, str] | None,
            "environment variables to be set before running the job",
        ] = None,
        account: Annotated[str | None, "the account to be used for the job"] = None,
        partition: Annotated[str | None, "the partition to be used for the job"] = None,
        reservation: Annotated[
            str | None, "the reservation to be used for the job"
        ] = None,
    ) -> dict:
        """Submit a job."""
        return self.client.submit(
            system_name,
            working_dir,
            script_str,
            script_local_path,
            script_remote_path,
            env_vars,
            account,
            partition,
            reservation,
        )

    @tool()
    @cachetools.func.ttl_cache(maxsize=10, ttl=20)
    def job_info(
        self,
        system_name: Annotated[str, "the system name where the filesystem belongs to"],
        jobid: Annotated[str | None, "the ID of the job"] = None,
        allusers: Annotated[
            bool, "whether to return jobs of all users or only the current user"
        ] = False,
        account: Annotated[
            str | None,
            "an account to filter the jobs by."
            + " It will only be taken into account when you are not specifying a jobid.",
        ] = None,
        name: Annotated[
            str | None,
            "a job name to filter the jobs by."
            + "It will only be taken into account when you are not specifying a jobid.",
        ] = None,
        time_window: Annotated[
            str | None,
            "how far back to look for historical (completed, failed, cancelled…) jobs."
            + " Pending and running jobs are always returned."
            + " Accepted values are 1h, 8h, 24h, 3d and 7d."
            + " It will only be taken into account when you are not specifying a jobid."
            + " Has no effect on PBS clusters.",
        ] = None,
    ) -> list:
        """Get job information. When the job is not specified, it will return all the
        jobs.
        """
        return self.client.job_info(
            system_name, jobid, allusers, account, name, time_window
        )

    @tool()
    @cachetools.func.ttl_cache(maxsize=10, ttl=60)
    def job_metadata(
        self,
        system_name: Annotated[str, "the system name where the filesystem belongs to"],
        jobid: Annotated[str, "the ID of the job"],
    ) -> dict:
        """Get job metadata."""
        return self.client.job_metadata(system_name, jobid)

    @tool()
    def cancel_job(
        self,
        system_name: Annotated[str, "the system name where the filesystem belongs to"],
        jobid: Annotated[str, "the ID of the job"],
    ) -> dict:
        """Cancel a job."""
        return self.client.cancel_job(system_name, jobid)

    @tool()
    def attach_to_job(
        self,
        system_name: Annotated[str, "the system name where the filesystem belongs to"],
        jobid: Annotated[str, "the ID of the job"],
        command: Annotated[str, "the command to be executed"],
    ) -> dict:
        """Attach a process to a job."""
        return self.client.attach_to_job(system_name, jobid, command)
