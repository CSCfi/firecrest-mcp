"""Tests for the job tools, which reach only the user's own jobs and cache the job
list."""

import asyncio

import pytest
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from firecrest_mcp.tools.compute import JOB_INFO_TTL, FirecrestComputeToolsMixin

MINE = {"jobId": 1, "user": "me"}
THEIRS = {"jobId": 2, "user": "someone"}


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


def test_own_job_by_id(mock_client):
    """The user's own job is returned when asked for by ID, and the user's name is
    fetched only once."""
    tools = Tools(mock_client, [MINE])
    assert call(tools, "job_info", "1") == [MINE]
    call(tools, "job_metadata", "1")
    tools.client.job_metadata.assert_called_once()
    tools.attach_to_job("lumi", "1", "rocm-smi")
    tools.client.attach_to_job.assert_called_once()
    tools.cancel_job("lumi", "1")
    tools.client.cancel_job.assert_called_once()
    tools.client.userinfo.assert_called_once()


@pytest.mark.parametrize(
    ("tool", "args"),
    [
        ("job_info", []),
        ("job_metadata", []),
        ("attach_to_job", ["rocm-smi"]),
        ("cancel_job", []),
    ],
)
def test_other_users_job_by_id_denied(tool, args, mock_client):
    """Another user's job is refused when asked for by ID, including a job FirecREST
    reports without an owner."""
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
