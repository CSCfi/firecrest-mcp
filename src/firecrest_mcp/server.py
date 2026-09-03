#!/usr/bin/env python3

from fastmcp import FastMCP
from fastmcp.dependencies import Depends

import firecrest
from firecrest.v2 import ExternalUpload, ExternalDownload, Firecrest

import argparse
import jwt
import os
import pathlib
import time
from typing import Annotated, Any, List


class TokenAuth:
    def __init__(self):
        pass

    def _is_token_valid(self, token: str) -> bool:
        try:
            payload = jwt.decode(
                token,
                options={"verify_signature": False, "verify_exp": False, "verify_aud": False},
            )
            return time.time() <= payload["exp"]
        except Exception:
            return False

    def get_access_token(self):
        token = os.getenv("FIRECREST_TOKEN", None)
        if not token:
            raise RuntimeError("Environment variable FIRECREST_TOKEN is not defined.")
        if not self._is_token_valid(token):
            raise RuntimeError("Token is invalid or has expired.")
        return token


class FirecrestClientWrapper:
    def __init__(self):
        self.client = None

    def get_client(self):
        return self.client

    def set_client(self, client):
        self.client = client


mcp = FastMCP("FirecREST v2")
client_wrapper = FirecrestClientWrapper()

#
# Status
#

@mcp.tool
def systems(client: Firecrest = Depends(client_wrapper.get_client)) -> List[dict]:
    """Returns available systems."""
    return client.systems()

@mcp.tool
def nodes(
    system_name: Annotated[str, "the system name where the nodes belong to"],
    client: Firecrest = Depends(client_wrapper.get_client),
) -> List[dict]:
    """Returns nodes of the system."""
    return client.nodes(system_name)

@mcp.tool
def reservations(
    system_name: Annotated[str, "the system name where the reservations belong to"],
    client: Firecrest = Depends(client_wrapper.get_client),
) -> List[dict]:
    """Returns reservations defined in the system."""
    return client.reservations(system_name)

@mcp.tool
def partitions(
    system_name: Annotated[str, "the system name where the partitions belong to"],
    client: Firecrest = Depends(client_wrapper.get_client),
) -> List[dict]:
    """Returns partitions defined in the system."""
    return client.partitions(system_name)

@mcp.tool
def userinfo(
    system_name: Annotated[str, "the system name"],
    client: Firecrest = Depends(client_wrapper.get_client),
) -> dict:
    """Returns user and groups information."""
    return client.userinfo(system_name)

#
# Filesystem
#

@mcp.tool
def list_files(
    system_name: Annotated[str, "the system name where the filesystem belongs to"],
    path: Annotated[str, "the absolute target path"],
    show_hidden: Annotated[bool, "Show hidden files"] = False,
    recursive: Annotated[bool, "recursively list directories encountered"] = False,
    numeric_uid: Annotated[bool, "list numeric user and group IDs"] = False, 
    dereference: Annotated[
        bool,
        "when showing file information for a symbolic link,"
        + " show information for the file the link references rather than for the link itself",
    ] = False,
    client: Firecrest = Depends(client_wrapper.get_client),
) -> List[dict]:
    """Returns a list of files in a directory."""
    return client.list_files(
        system_name, path, show_hidden, recursive, numeric_uid, dereference,
    )

@mcp.tool
def head(
    system_name: Annotated[str, "the system name where the filesystem belongs to"],
    path: Annotated[str, "the absolute target path of the file"],
    num_bytes: Annotated[int | None, "the output will be the first NUM bytes of each file"] = None,
    num_lines: Annotated[int | None, "the output will be the first NUM lines of each file"] = None,
    exclude_trailing: Annotated[
        bool,
        "the output will be the whole file, without the last NUM bytes/lines of each file."
        + "NUM should be specified in the respective argument through num_bytes or num_lines.",
    ] = False,
    client: Firecrest = Depends(client_wrapper.get_client),
) -> dict:
    """Display the beginning of a specified file. By default 10 lines will be returned. num_bytes
    and num_lines cannot be specified simultaneously.
    """
    return client.head(system_name, path, num_bytes, num_lines, exclude_trailing)

@mcp.tool
def tail(
    system_name: Annotated[str, "the system name where the filesystem belongs to"],
    path: Annotated[str, "the absolute target path of the file"],
    num_bytes: Annotated[int | None, "The output will be the last NUM bytes of each file"] = None,
    num_lines: Annotated[int | None, "The output will be the last NUM lines of each file"] = None,
    exclude_beginning: Annotated[
        bool,
        "The output will be the whole file, without the first NUM bytes/lines of each file."
        + "NUM should be specified in the respective argument through num_bytes or num_lines.",
    ] = False,
    client: Firecrest = Depends(client_wrapper.get_client),
) -> dict:
    """Display the ending of a specified file. By default, 10 lines will be returned. num_bytes and
    num_lines cannot be specified simultaneously.
    """
    return client.head(system_name, path, num_bytes, num_lines, exclude_trailing)

@mcp.tool
def view(
    system_name: Annotated[str, "the system name where the filesystem belongs to"],
    path: Annotated[str, "the absolute target path of the file"],
    client: Firecrest = Depends(client_wrapper.get_client),
) -> str:
    """View full file content (up to 5MB files)"""
    return client.view(system_name, path)

@mcp.tool
def checksum(
    system_name: Annotated[str, "the system name where the filesystem belongs to"],
    path: Annotated[str, "the absolute target path of the file"],
    client: Firecrest = Depends(client_wrapper.get_client),
) -> dict:
    """Calculate the SHA256 (256-bit) checksum of a specified file."""
    return client.checksum(system_name, path)

@mcp.tool
def file_type(
    system_name: Annotated[str, "the system name where the filesystem belongs to"],
    path: Annotated[str, "the absolute target path of the file"],
    client: Firecrest = Depends(client_wrapper.get_client),
) -> str:
    """Uses the file linux application to determine the type of a file."""
    return client.file_type(system_name, path)

@mcp.tool
def chmod(
    system_name: Annotated[str, "the system name where the filesystem belongs to"],
    path: Annotated[str, "the absolute target path of the file"],
    mode: Annotated[str, "same as numeric mode of linux chmod tool"],
    client: Firecrest = Depends(client_wrapper.get_client),
) -> dict:
    """Changes the file mod bits of a given file according to the specified mode."""
    return client.chmod(system_name, path, mode)

@mcp.tool
def chown(
    system_name: Annotated[str, "the system name where the filesystem belongs to"],
    path: Annotated[str, "the absolute target path of the file"],
    owner: Annotated[str, "owner ID for target"],
    group: Annotated[str, "group ID for target"],
    client: Firecrest = Depends(client_wrapper.get_client),
) -> dict:
    """Changes the user and/or group ownership of a given file. If only owner or group information
    is passed, only that information will be updated.
    """
    return client.chown(system_name, path, owner, group)

@mcp.tool
def stat(
    system_name: Annotated[str, "the system name where the filesystem belongs to"],
    path: Annotated[str, "the absolute target path of the file"],
    dereference: Annotated[bool, "follow symbolic links"] = False,
    client: Firecrest = Depends(client_wrapper.get_client),
) -> dict:
    """Uses the stat linux application to determine the status of a file on the system's
    filesystem. The result follows: https://docs.python.org/3/library/os.html#os.stat_result.
    """
    return client.stat(system_name, path, dereference)

@mcp.tool
def symlink(
    system_name: Annotated[str, "the system name where the filesystem belongs to"],
    source_path: Annotated[str, "the absolute path to the file the link points to"],
    link_path: Annotated[str, "the absolute path to the symlink"],
    client: Firecrest = Depends(client_wrapper.get_client),
) -> dict:
    """Create a symbolic link."""
    return client.symlink(system_name, source_path, link_path)

@mcp.tool
def mkdir(
    system_name: Annotated[str, "the system name where the filesystem belongs to"],
    path: Annotated[str, "the absolute target path to the new directory"],
    create_parents: Annotated[bool, "create intermediate parent directories"] = False,
    client: Firecrest = Depends(client_wrapper.get_client),
) -> dict:
    """Create a directory."""
    return client.mkdir(system_name, path, create_parents)

@mcp.tool
def mv(
    system_name: Annotated[str, "the system name where the filesystem belongs to"],
    source_path: Annotated[str, "the absolute source path"],
    target_path: Annotated[str, "the absolute target path"],
    account: Annotated[str | None, "the account to be used for the transfer job"] = None,
    blocking: Annotated[bool, "whether to wait dor the job to complete"] = True,
    timeout: Annotated[float | None, "the maximum time to wait for the job to complete"] = None,
    client: Firecrest = Depends(client_wrapper.get_client),
) -> dict:
    """Rename/move a file, directory, or symlink at the source_path to the target_path on
    system_name’s filesystem. This operation runs in a job.
    """
    return client.mv(system_name, source_path, target_path, account, blocking, timeout)

@mcp.tool
def compress(
    system_name: Annotated[str, "the system name where the filesystem belongs to"],
    source_path: Annotated[str, "the absolute path to the source directory"],
    target_path: Annotated[str, "the absolute path to the newly created compressed file"],
    dereference: Annotated[bool, "dereference links when compressing"] = False,
    compression: Annotated[
        str,
        "compression algorithm to use (one of 'none', 'gzip', 'bzip2', 'xz')."
        + "Default is 'gzip'.",
    ] = "gzip",
    match_pattern: Annotated[str | None, "regex pattern to filter files to compress"] = None,
    account: Annotated[
        str | None,
        "the account to be used for the transfer job"
        + " (only relevant when the compression operation is not done directly)",
    ] = None,
    blocking: Annotated[
        bool,
        "whether to wait dor the job to complete"
        + " (only relevant when the compression operation is not done directly)",
    ] = True,
    client: Firecrest = Depends(client_wrapper.get_client),
) -> None:
    """Compress a directory or file."""
    return client.compress(
        system_name, source_path, target_path, dereference,
        compression, match_pattern, account, blocking,
    )

@mcp.tool
def extract(
    system_name: Annotated[str, "the system name where the filesystem belongs to"],
    source_path: Annotated[str, "the absolute path to the archive"],
    target_path: Annotated[str, "the absolute path to target directory"],
    compression: Annotated[
        str,
        "compression algorithm to use (one of 'none', 'gzip', 'bzip2', 'xz')."
        + "Default is 'gzip'.",
    ] = "gzip",
    account: Annotated[
        str | None,
        "the account to be used for the transfer job"
        + " (only relevant when the extract operation is not done directly)",
    ] = None,
    blocking: Annotated[
        bool,
        "whether to wait dor the job to complete"
        + " (only relevant when the extract operation is not done directly)",
    ] = True,
    client: Firecrest = Depends(client_wrapper.get_client),
) -> None:
    """Extract compressed archives."""
    return client.extract(system_name, source_path, target_path, compression, account, blocking)

@mcp.tool
def wait_for_job(
    system_name: Annotated[str, "the system name where the filesystem belongs to"],
    jobid: Annotated[str | None, "the ID of the job"] = None,
    timeout: Annotated[float | None, "the maximum time to wait for the job to complete"] = None,
    not_found_timeout: Annotated[
        float,
        "the maximum time to wait for the job to be available in the scheduler, in seconds."
        + "Slurm or other scheduler will need a few seconds before updating the database."
        + "If the job is not found within this time, the function will raise an exception.",
    ] = 20.0,
    client: Firecrest = Depends(client_wrapper.get_client),
) -> List[Any]:
    """Wait for a job to complete. When the job is completed, it will return the job information.
    """
    return client.wait_for_job(system_name, jobid, timeout, not_found_timeout)

@mcp.tool
def cp(
    system_name: Annotated[str, "the system name where the filesystem belongs to"],
    source_path: Annotated[str, "the absolute source path"],
    target_path: Annotated[str, "the absolute target path"],
    dereference: Annotated[bool, "dereference links when copying"] = False,
    blocking: Annotated[bool, "whether to wait dor the job to complete"] = True,
    account: Annotated[str | None, "the account to be used for the transfer job"] = None,
    timeout: Annotated[float | None, "the maximum time to wait for the job to complete"] = None,
    client: Firecrest = Depends(client_wrapper.get_client),
) -> dict:
    """Copies file from source_path to target_path."""
    return client.cp(
        system_name, source_path, target_path, dereference, blocking, account, timeout,
    )

@mcp.tool
def rm(
    system_name: Annotated[str, "the system name where the filesystem belongs to"],
    path: Annotated[str, "the absolute target path"],
    account: Annotated[
        str | None,
        "the account to be used for the transfer job"
        + " (only relevant when the file is not deleted directly)",
    ] = None,
    blocking: Annotated[
        bool,
        "whether to wait dor the job to complete"
        + " (only relevant when the file is not deleted directly)",
    ] = True,
    timeout: Annotated[float | None, "the maximum time to wait for the job to complete"] = None,
    client: Firecrest = Depends(client_wrapper.get_client),
) -> dict | None:
    """Delete a file. First the client will try to delete the file directly, and if it fails with a
    timeout, it will launch a job to delete the file.
    """
    return client.rm(system_name, path, account, blocking, timeout)

@mcp.tool
def upload(
    system_name: Annotated[str, "the system name where the filesystem belongs to"],
    local_file: Annotated[
        str | pathlib.Path,
        "the local file’s path to be uploaded (can be relative)"
        + "or a file-like object (implements .read())",
    ],
    directory: Annotated[
        str,
        "the absolut target path of the directory where the file will be uploaded",
    ],
    filename: Annotated[str, "the name of the file in the target directory"],
    account: Annotated[
        str | None,
        "the account to be used for the transfer job"
        + " (only relevant when the file is larger than MAX_DIRECT_UPLOAD_SIZE)",
    ] = None,
    blocking: Annotated[
        bool,
        "whether to wait dor the job to complete"
        + " (only relevant when the file is larger than MAX_DIRECT_UPLOAD_SIZE)",
    ] = True,
    transfer_method: Annotated[
        str,
        "the method to be used for the upload of large files."
        + "Supported methods: 's3', 'streamer', 'wormhole'.",
    ] = "s3",
    file_size: Annotated[
        int | None,
        "the size of the file in bytes. Required for the local_file is a file-like object.",
    ] = None,
    client: Firecrest = Depends(client_wrapper.get_client),
) -> ExternalUpload | None:
    """Upload a file to the system. Small files will be uploaded directly to FirecREST and will be
    immediately available. The function will return None in this case. Large files will be uploaded
    in parts to the staging area of FirecREST and then moved to the target directory in a job. The
    function will return the transfer job information in this case.
    """
    return client.upload(
        system_name, local_file, directory, filename,
        account, blocking, transfer_method, file_size,
    )

@mcp.tool
def download(
    system_name: Annotated[str, "the system name where the filesystem belongs to"],
    source_path: Annotated[str, "the absolute source path of the file"],
    target_path: Annotated[
        str | pathlib.Path,
        "the target path in the local filesystem (can be relative path)",
    ],
    account: Annotated[
        str | None,
        "the account to be used for the transfer job"
        + " (only relevant when the file is larger than MAX_DIRECT_UPLOAD_SIZE)",
    ] = None,
    blocking: Annotated[bool, "whether to wait dor the job to complete"] = True,
    transfer_method: Annotated[
        str,
        "the method to be used for the upload of large files."
        + "Supported methods: 's3', 'streamer', 'wormhole'.",
    ] = "s3",
    client: Firecrest = Depends(client_wrapper.get_client),
) -> ExternalDownload:
    """Download a file from the remote system."""
    return client.download(
        system_name, source_path, target_path, account, blocking, transfer_method,
    )

#
# Compute
#

@mcp.tool
def submit(
    system_name: Annotated[str, "the system name where the filesystem belongs to"],
    working_dir: Annotated[str | None, "the working directory of the job"],
    script_str: Annotated[str | None, "the job script"] = None,
    script_local_path: Annotated[str | None, "path to the job script"] = None,
    script_remote_path: Annotated[
        str | None, "path to the job script on the remote filesystem"
    ] = None,
    env_vars: Annotated[
        dict[str, str], "environment variables to be set before running the job"
    ] = None,
    account: Annotated[str | None, "the account to be used for the job"] = None,
    partition: Annotated[str | None, "the partition to be used for the job"] = None,
    reservation: Annotated[str | None, "the reservation to be used for the job"] = None,
    client: Firecrest = Depends(client_wrapper.get_client),
) -> dict:
    """Submit a job."""
    return client.submit(
        system_name, working_dir, script_str, script_local_path, script_remote_path,
        env_vars, account, partition, reservation,
    )

@mcp.tool
def job_info(
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
    client: Firecrest = Depends(client_wrapper.get_client),
) -> list:
    """Get job information. When the job is not specified, it will return all the jobs."""
    return client.job_info(system_name, jobid, allusers, account, name, time_window)

@mcp.tool
def job_metadata(
    system_name: Annotated[str, "the system name where the filesystem belongs to"],
    jobid: Annotated[str, "the ID of the job"],
    client: Firecrest = Depends(client_wrapper.get_client),
) -> dict:
    """Get job metadata."""
    return client.job_metadata(system_name, jobid)

@mcp.tool
def cancel_job(
    system_name: Annotated[str, "the system name where the filesystem belongs to"],
    jobid: Annotated[str, "the ID of the job"],
    client: Firecrest = Depends(client_wrapper.get_client),
) -> dict:
    """Cancel a job."""
    return client.cancel_job(system_name, jobid)

@mcp.tool
def attach_to_job(
    system_name: Annotated[str, "the system name where the filesystem belongs to"],
    jobid: Annotated[str, "the ID of the job"],
    command: Annotated[str, "the command to be executed"],
    client: Firecrest = Depends(client_wrapper.get_client),
) -> dict:
    """Attach a process to a job."""
    return client.attach_to_job(system_name, jobid, command)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("firecrest_url", type=str, help="FirecREST's URL")
    parser.add_argument(
        "--transport", "-t", type=str, default="stdio",
        help="MCP transport protocol to use [choices: stdio, http, sse, streamable-http]",
    )
    parser.add_argument(
        "--host", type=str, default="127.0.0.1",
        help="MCP host to bind to when using http transport (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port", "-p", type=str, default="8000",
        help="MCP port to bind to when using http transport (default: 8000)",
    )
    args = parser.parse_args()

    firecrest_client = Firecrest(firecrest_url=args.firecrest_url, authorization=TokenAuth())
    client_wrapper.set_client(firecrest_client)

    kwargs = {"transport": args.transport}
    if args.transport != "stdio":
        mcp_kwargs.update({"host": args.host, "port": args.port})
    mcp.run(**kwargs)
