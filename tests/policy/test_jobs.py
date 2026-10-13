"""Tests that the job tools only reach the user's own jobs."""

from unittest.mock import create_autospec

import pytest
from fastmcp.exceptions import ToolError
from firecrest.v2 import Firecrest

from firecrest_mcp.tools.compute import FirecrestComputeToolsMixin

MINE = {"jobId": 1, "user": "me"}
THEIRS = {"jobId": 2, "user": "someone"}


# The tools with a mock FirecREST client whose user is "me".
class Tools(FirecrestComputeToolsMixin):
    def __init__(self, jobs):
        self.client = create_autospec(Firecrest, instance=True)
        self.client.userinfo.return_value = {"user": {"name": "me"}}
        self.client.job_info.return_value = jobs


def call(tools, name, *args):
    # Through getattr, as ty doesn't see the ttl_cache-wrapped tools as methods.
    return getattr(tools, name)("lumi", *args)


def test_job_list_has_only_own_jobs():
    """Listing jobs never asks for, or returns, other users' jobs."""
    tools = Tools([MINE, THEIRS])
    assert call(tools, "job_info") == [MINE]
    assert tools.client.job_info.call_args.kwargs["allusers"] is False


def test_own_job_by_id():
    """The user's own job is returned when asked for by ID, and the user's name is
    fetched only once."""
    tools = Tools([MINE])
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
def test_other_users_job_by_id_denied(tool, args):
    """Another user's job is refused when asked for by ID, including a job FirecREST
    reports without an owner."""
    for jobs in [[THEIRS], [{"jobId": 2}]]:
        tools = Tools(jobs)
        with pytest.raises(ToolError, match="Job 2 is not one of your jobs"):
            call(tools, tool, "2", *args)
        tools.client.job_metadata.assert_not_called()
        tools.client.attach_to_job.assert_not_called()
        tools.client.cancel_job.assert_not_called()
