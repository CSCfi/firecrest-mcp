"""Tests for the job tools, which reach only the user's own jobs and cache the job
list."""

import asyncio
import shlex

import httpx
import pytest
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from firecrest import UnexpectedStatusException

from firecrest_mcp.tools.compute import JOB_INFO_TTL, FirecrestComputeToolsMixin

MINE = {"jobId": 1, "user": "me"}
THEIRS = {"jobId": 2, "user": "someone"}
# An output file of attach_to_job that the default config allows.
OUTPUT_PATH = "/scratch/project_1/out.txt"


# The tools with a mock FirecREST client whose user is "me".
class Tools(FirecrestComputeToolsMixin):
    def __init__(self, client, jobs):
        self.client = client
        self.client.userinfo.return_value = {"user": {"name": "me"}}
        self.client.job_info.return_value = jobs


def call(tools, name, *args):
    # Through getattr, as ty doesn't see the ttl_cache-wrapped tools as methods.
    return getattr(tools, name)("lumi", *args)


def test_job_list_has_only_own_jobs(mock_client):
    """Listing jobs never asks for, or returns, other users' jobs."""
    tools = Tools(mock_client, [MINE, THEIRS])
    assert call(tools, "job_info") == [MINE]
    assert tools.client.job_info.call_args.kwargs["allusers"] is False


def test_own_job_by_id(config, mock_client):
    """The user's own job is returned when asked for by ID, and the user's name is
    fetched only once."""
    config()
    tools = Tools(mock_client, [MINE])
    assert call(tools, "job_info", "1") == [MINE]
    call(tools, "job_metadata", "1")
    tools.client.job_metadata.assert_called_once()
    tools.attach_to_job("lumi", "1", "rocm-smi", OUTPUT_PATH)
    tools.client.attach_to_job.assert_called_once()
    tools.cancel_job("lumi", "1")
    tools.client.cancel_job.assert_called_once()
    tools.client.userinfo.assert_called_once()


@pytest.mark.parametrize(
    ("tool", "args"),
    [
        ("job_info", []),
        ("job_metadata", []),
        ("attach_to_job", ["rocm-smi", OUTPUT_PATH]),
        ("cancel_job", []),
    ],
)
def test_other_users_job_by_id_denied(tool, args, config, mock_client):
    """Another user's job is refused when asked for by ID, including a job FirecREST
    reports without an owner."""
    config()
    for jobs in [[THEIRS], [{"jobId": 2}]]:
        tools = Tools(mock_client, jobs)
        with pytest.raises(ToolError, match="Job 2 is not one of your jobs"):
            call(tools, tool, "2", *args)
        tools.client.job_metadata.assert_not_called()
        tools.client.attach_to_job.assert_not_called()
        tools.client.cancel_job.assert_not_called()


def test_job_list_after_submit(config, mock_client):
    """A job list right after submit asks FirecREST again and has the new job."""
    config()
    new_job = {"jobId": 3, "user": "me"}
    tools = Tools(mock_client, [MINE])
    assert call(tools, "job_info") == [MINE]
    tools.submit("lumi", "/scratch/project_1/x", script_str="#!/bin/bash")
    tools.client.job_info.return_value = [MINE, new_job]
    assert call(tools, "job_info") == [MINE, new_job]


def test_job_list_after_cancel(mock_client):
    """A job list right after cancel_job asks FirecREST again and shows the change."""
    cancelled_job = {"jobId": 1, "user": "me", "status": {"state": "CANCELLED"}}
    tools = Tools(mock_client, [MINE])
    assert call(tools, "job_info") == [MINE]
    tools.cancel_job("lumi", "1")
    tools.client.job_info.return_value = [cancelled_job]
    assert call(tools, "job_info") == [cancelled_job]


def test_job_list_description_gives_cache_time(mock_client):
    """The description of job_info that the agent sees gives the cache time."""
    server = FastMCP("test")
    server.add_tool(Tools(mock_client, []).job_info)
    listed_tools = asyncio.run(server.list_tools())
    # job_info is the only tool on this server.
    description = listed_tools[0].description
    assert description is not None
    assert f"up to {JOB_INFO_TTL} seconds old" in description


def status_error(status_code, message):
    """Return the error that pyfirecrest raises when FirecREST answers the attach
    request with this status and message."""
    request = httpx.Request("PUT", "https://firecrest.test/compute/lumi/jobs/1/attach")
    response = httpx.Response(status_code, json={"message": message}, request=request)
    return UnexpectedStatusException([response], 204)


def sent_shell_line(tools):
    """Return the words of the shell line that attach_to_job sent to FirecREST."""
    return shlex.split(tools.client.attach_to_job.call_args.kwargs["command"])


def test_attach_runs_whole_command_in_bash(config, mock_client):
    """The whole command, with its ";" and quotes, goes to bash in the job. Its
    output and errors go to the file, and its stdin is /dev/null."""
    config()
    tools = Tools(mock_client, [MINE])
    command = "echo 'a b'; hostname > x"
    result = tools.attach_to_job("lumi", "1", command, OUTPUT_PATH)
    assert sent_shell_line(tools) == [
        "bash",
        "-c",
        command,
        ">",
        OUTPUT_PATH,
        "2>&1",
        "<",
        "/dev/null",
    ]
    assert result == {
        "output_path": OUTPUT_PATH,
        "status": "finished",
        "exit_status": 0,
    }


def test_attach_timeout_returns_path(config, mock_client):
    """When FirecREST stops waiting for the command, the result gives the file,
    which keeps the output written until then."""
    config()
    tools = Tools(mock_client, [MINE])
    tools.client.attach_to_job.side_effect = status_error(
        504, "Command execution timeout limit exceeded."
    )
    result = tools.attach_to_job("lumi", "1", "sleep 600", OUTPUT_PATH)
    assert result["output_path"] == OUTPUT_PATH
    assert result["status"] == "killed"
    assert "Submit longer work as a job" in result["note"]


def test_attach_exit_status(config, mock_client):
    """A command that exits with an error gives its exit status and the file."""
    config()
    tools = Tools(mock_client, [MINE])
    tools.client.attach_to_job.side_effect = status_error(
        500, "Unexpected Slurm command response. exit_status:3 std_err:"
    )
    result = tools.attach_to_job("lumi", "1", "exit 3", OUTPUT_PATH)
    assert result == {
        "output_path": OUTPUT_PATH,
        "status": "finished",
        "exit_status": 3,
    }


def test_attach_other_error_raised(config, mock_client):
    """An error without an exit status, which says nothing about the file, goes
    through unchanged."""
    config()
    tools = Tools(mock_client, [MINE])
    error = status_error(500, "Something else went wrong.")
    tools.client.attach_to_job.side_effect = error
    with pytest.raises(UnexpectedStatusException) as raised:
        tools.attach_to_job("lumi", "1", "hostname", OUTPUT_PATH)
    assert raised.value is error
