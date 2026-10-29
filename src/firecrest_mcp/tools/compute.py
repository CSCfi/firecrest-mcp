"""Tools for Slurm jobs: submitting, querying, cancelling and attaching to them."""

from typing import Annotated

import cachetools.func
from fastmcp.exceptions import ToolError
from fastmcp.tools import tool
from firecrest.v2 import Firecrest

from firecrest_mcp.policy import check_local_paths, load_cluster_policy, own_jobs
from firecrest_mcp.tools.params import SystemName


class FirecrestComputeToolsMixin:
    client: Firecrest

    @tool()
    def submit(
        self,
        system_name: SystemName,
        working_dir: Annotated[str | None, "the working directory of the job"],
        script_str: Annotated[str | None, "the job script"] = None,
        script_local_path: Annotated[str | None, "path to the job script"] = None,
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
        cluster = load_cluster_policy()
        cluster.check_remote_paths(working_dir, script_remote_path)
        check_local_paths(script_local_path)
        account, partition = cluster.checked_job_options(
            account, partition, reservation
        )
        return self.client.submit(
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

    @tool()
    @cachetools.func.ttl_cache(maxsize=10, ttl=20)
    def job_info(
        self,
        system_name: SystemName,
        jobid: Annotated[str | None, "the ID of the job"] = None,
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
        """Get information about your jobs. When the job is not specified, it will
        return all of them. Other users' jobs are not available.
        """
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
    @cachetools.func.ttl_cache(maxsize=10, ttl=60)
    def job_metadata(
        self,
        system_name: SystemName,
        jobid: Annotated[str, "the ID of the job"],
    ) -> dict:
        """Get the metadata of one of your jobs."""
        own_jobs(
            self.client,
            system_name,
            self.client.job_info(system_name, jobid=jobid),
            jobid,
        )
        return self.client.job_metadata(system_name, jobid=jobid)

    @tool()
    def cancel_job(
        self,
        system_name: SystemName,
        jobid: Annotated[str, "the ID of the job"],
    ) -> dict:
        """Cancel one of your jobs."""
        own_jobs(
            self.client,
            system_name,
            self.client.job_info(system_name, jobid=jobid),
            jobid,
        )
        return self.client.cancel_job(system_name, jobid=jobid)

    @tool()
    def attach_to_job(
        self,
        system_name: SystemName,
        jobid: Annotated[str, "the ID of the job"],
        command: Annotated[str, "the command to be executed"],
    ) -> dict:
        """Run a command inside one of your running jobs."""
        own_jobs(
            self.client,
            system_name,
            self.client.job_info(system_name, jobid=jobid),
            jobid,
        )
        return self.client.attach_to_job(system_name, jobid=jobid, command=command)
