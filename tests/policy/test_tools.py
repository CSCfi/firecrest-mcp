"""Tests of the tools with a mock client: that every tool checks its arguments, and
the behaviour of submit, read_file and chgrp.
"""

import inspect
from unittest.mock import create_autospec

import pytest
from fastmcp.exceptions import ToolError
from firecrest.v2 import Firecrest

from firecrest_mcp.tools.compute import FirecrestComputeToolsMixin
from firecrest_mcp.tools.filesystem import FirecrestFilesystemToolsMixin
from firecrest_mcp.tools.status import FirecrestStatusToolsMixin

# Allowed and denied by the default CONFIG in conftest.py.
ALLOWED = "/scratch/project_1/x"
DENIED = "/etc/x"
ALLOWED_LOCAL = "data/x"
DENIED_LOCAL = "x"

# Each tool with its remote path arguments, local path arguments and its other
# arguments (besides system_name). Every path argument must be checked.
TOOL_CALLS = [
    ("list_files", ["path"], [], {}),
    ("read_file", ["path"], [], {}),
    ("checksum", ["path"], [], {}),
    ("chmod", ["path"], [], {"mode": "700"}),
    ("chgrp", ["path"], [], {"group": "project_1"}),
    ("stat", ["path"], [], {}),
    ("symlink", ["source_path", "link_path"], [], {}),
    ("mkdir", ["path"], [], {}),
    ("mv", ["source_path", "target_path"], [], {}),
    ("compress", ["source_path", "target_path"], [], {}),
    ("extract", ["source_path", "target_path"], [], {}),
    ("cp", ["source_path", "target_path"], [], {}),
    ("rm", ["path"], [], {}),
    ("upload", ["directory"], ["local_file"], {"filename": "f"}),
    ("download", ["source_path"], ["target_path"], {}),
    ("submit", ["working_dir", "script_remote_path"], [], {}),
    ("submit", ["working_dir"], ["script_local_path"], {}),
]

# Tools without arguments that the config controls. Every other tool must be in
# TOOL_CALLS, so that its arguments are tested.
UNCHECKED_TOOLS = {
    "systems",
    "partitions",
    "reservations",
    "userinfo",
    "job_info",
    "job_metadata",
    "cancel_job",
    "attach_to_job",
}

# Tools with an account argument, which defaults to default_account.
ACCOUNT_TOOLS = [
    (name, remote, local, other)
    for name, remote, local, other in TOOL_CALLS
    if name in {"mv", "compress", "extract", "cp", "rm", "upload", "download"}
]


def tool_call(name, *args):
    """Return the entry of TOOL_CALLS for a tool, with the given arguments."""
    return next(c for c in TOOL_CALLS if c[0] == name and set(args) <= {*c[1], *c[2]})


# The tools with a mock FirecREST client, so no real system is contacted. The mock
# has the client's signatures, so a call with a wrong argument name fails.
class Tools(FirecrestFilesystemToolsMixin, FirecrestComputeToolsMixin):
    def __init__(self):
        self.client = create_autospec(Firecrest, instance=True)


@pytest.fixture
def tools(config, tmp_path):
    """Tools with the default config and an allowed local directory."""
    config()
    (tmp_path / "data").mkdir()
    return Tools()


def call(tools, name, remote_args, local_args, other_args, **overrides):
    kwargs = (
        dict.fromkeys(remote_args, ALLOWED)
        | dict.fromkeys(local_args, ALLOWED_LOCAL)
        | other_args
        | overrides
    )
    return getattr(tools, name)("lumi", **kwargs)


def client_method(tools, name):
    """Return the client method a tool calls, which differs for some tools."""
    return getattr(
        tools.client, {"read_file": "view", "chgrp": "chown"}.get(name, name)
    )


def client_args(tools, method):
    """Return the arguments of the last call to a client method by parameter name,
    with defaults filled in."""
    call = getattr(tools.client, method).call_args
    bound = inspect.signature(getattr(Firecrest, method)).bind(
        None, *call.args, **call.kwargs
    )
    bound.apply_defaults()
    return bound.arguments


def ids(calls):
    return [f"{c[0]}-{'-'.join(c[1] + c[2])}" for c in calls]


def test_every_tool_is_in_tool_calls():
    """A new tool must be added to TOOL_CALLS or to UNCHECKED_TOOLS. The tools are
    listed as server.py registers them: every callable non-dunder attribute."""

    class Wrapper(
        FirecrestComputeToolsMixin,
        FirecrestFilesystemToolsMixin,
        FirecrestStatusToolsMixin,
    ):
        pass

    tools = {
        name
        for name in dir(Wrapper)
        if callable(getattr(Wrapper, name)) and not name.startswith("__")
    }
    assert tools == {c[0] for c in TOOL_CALLS} | UNCHECKED_TOOLS, (
        "Add a new tool to TOOL_CALLS, or to UNCHECKED_TOOLS if the config controls"
        " none of its arguments. Remove a deleted tool from them."
    )


@pytest.mark.parametrize(
    ("name", "remote_args", "local_args", "other_args"), TOOL_CALLS, ids=ids(TOOL_CALLS)
)
def test_tool_with_allowed_arguments_calls_client(
    tools, name, remote_args, local_args, other_args
):
    """Each tool calls the client when its arguments are allowed."""
    call(tools, name, remote_args, local_args, other_args)
    client_method(tools, name).assert_called_once()


@pytest.mark.parametrize(
    ("name", "remote_args", "local_args", "other_args", "denied"),
    [
        pytest.param(name, remote, local, other, {arg: value}, id=f"{name}-{arg}")
        for name, remote, local, other in TOOL_CALLS
        for args, value in [(remote, DENIED), (local, DENIED_LOCAL)]
        for arg in args
    ]
    + [
        pytest.param(name, remote, local, other, {"account": "x"}, id=f"{name}-account")
        for name, remote, local, other in ACCOUNT_TOOLS + [tool_call("submit")]
    ]
    + [
        pytest.param(*tool_call("chgrp"), {"group": "other"}, id="chgrp-group"),
        pytest.param(*tool_call("submit"), {"partition": "x"}, id="submit-partition"),
        pytest.param(
            *tool_call("submit"), {"reservation": "x"}, id="submit-reservation"
        ),
    ],
)
def test_tool_with_denied_argument_does_not_call_client(
    tools, name, remote_args, local_args, other_args, denied
):
    """Any denied argument stops the tool before it calls the client."""
    with pytest.raises(ToolError, match="is not in"):
        call(tools, name, remote_args, local_args, other_args, **denied)
    client_method(tools, name).assert_not_called()


@pytest.mark.parametrize(
    ("name", "remote_args", "local_args", "other_args"),
    ACCOUNT_TOOLS,
    ids=ids(ACCOUNT_TOOLS),
)
def test_tool_uses_default_account(tools, name, remote_args, local_args, other_args):
    """A tool called without an account passes the default account as the client's
    account argument."""
    call(tools, name, remote_args, local_args, other_args)
    assert client_args(tools, name)["account"] == "project_1"


def test_upload_filename_cannot_escape_directory(tools):
    """A filename with '..' cannot move an upload out of its directory."""
    with pytest.raises(ToolError):
        tools.upload("lumi", "data/x", "/scratch/project_1", "../project_2/f")
    tools.client.upload.assert_not_called()


def submit(tools, script, **kwargs):
    """Submit a script and return the arguments the client got, by name."""
    tools.submit("lumi", kwargs.pop("working_dir", None), script_str=script, **kwargs)
    return client_args(tools, "submit")


@pytest.mark.parametrize(
    ("kwargs", "options"),
    [
        # Without arguments, a job gets the default account and partition.
        ({}, ("project_1", "small", None)),
        (
            {"account": "project_2", "partition": "debug", "reservation": "training"},
            ("project_2", "debug", "training"),
        ),
        # A comma-separated list is allowed if every item in it is listed.
        ({"partition": "small,debug"}, ("project_1", "small,debug", None)),
    ],
)
def test_submit_options(tools, kwargs, options):
    """The client gets the job's account, partition and reservation."""
    args = submit(tools, "#!/bin/bash", **kwargs)
    assert (args["account"], args["partition"], args["reservation"]) == options


def test_submit_overrides_script(tools):
    """The script's #SBATCH lines aren't checked, and the default account and
    partition are passed so that they override the script's."""
    args = submit(tools, "#SBATCH -A project_3 -p standard\n")
    assert (args["account"], args["partition"]) == ("project_1", "small")


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"account": "project_3"}, "Account 'project_3' is not in"),
        ({"partition": "standard"}, "Partition 'standard' is not in"),
        ({"partition": "small,standard"}, "Partition 'standard' is not in"),
        ({"reservation": "other"}, "Reservation 'other' is not in"),
        ({"reservation": "training,other"}, "Reservation 'other' is not in"),
        # An empty argument is not left to FirecREST's or Slurm's default.
        ({"account": ""}, "is not in"),
        ({"partition": ""}, "is not in"),
        ({"reservation": ""}, "is not in"),
    ],
)
def test_submit_denied(tools, kwargs, error):
    """Denied arguments stop the job."""
    with pytest.raises(ToolError, match=error):
        submit(tools, "#!/bin/bash\n", working_dir="/scratch/project_1", **kwargs)
    tools.client.submit.assert_not_called()


def test_submit_needs_exactly_one_script(tools):
    """Exactly one of the three script arguments must be given."""
    with pytest.raises(ToolError, match="Exactly one"):
        tools.submit("lumi", None)
    with pytest.raises(ToolError, match="Exactly one"):
        tools.submit("lumi", None, script_str="x", script_local_path=ALLOWED_LOCAL)
    tools.client.submit.assert_not_called()


def test_submit_without_default_partition(config):
    """Without default_partition, a partition must be given as an argument."""
    config('[lumi]\naccounts = ["p"]\ndefault_account = "p"\npartitions = ["small"]\n')
    tools = Tools()
    with pytest.raises(ToolError, match="No partition given"):
        tools.submit("lumi", None, script_str="#SBATCH -p small")
    tools.submit("lumi", None, script_str="#!/bin/bash", partition="small")
    tools.client.submit.assert_called_once()


@pytest.mark.parametrize(
    ("kwargs", "method", "expected"),
    [
        ({}, "view", "all"),
        ({"first_lines": 2}, "head", "first"),
        ({"last_lines": 2}, "tail", "last"),
    ],
)
def test_read_file(tools, kwargs, method, expected):
    """read_file reads the whole file, or its first or last lines, as text."""
    tools.client.view.return_value = "all"
    tools.client.head.return_value = {"content": "first", "startPosition": 0}
    tools.client.tail.return_value = {"content": "last", "startPosition": 0}
    assert tools.read_file("lumi", ALLOWED, **kwargs) == expected
    getattr(tools.client, method).assert_called_once()


def test_read_file_first_and_last_lines(tools):
    """Asking for both the first and the last lines is an error."""
    with pytest.raises(ToolError, match="at most one"):
        tools.read_file("lumi", ALLOWED, first_lines=1, last_lines=1)
    assert not tools.client.method_calls


def test_chgrp_keeps_owner(tools):
    """chgrp changes only the group: an empty owner leaves the owner as it is."""
    tools.chgrp("lumi", ALLOWED, "project_1")
    tools.client.chown.assert_called_once_with(
        "lumi", path=ALLOWED, owner="", group="project_1"
    )


def test_compress_has_no_match_pattern(tools):
    """match_pattern is never passed, as FirecREST puts it into a shell command
    without escaping it."""
    tools.compress("lumi", ALLOWED, ALLOWED)
    assert client_args(tools, "compress")["match_pattern"] is None


@pytest.mark.parametrize("mode", ["u+x", "700'; rm -rf ~; '", "7000a", "75", ""])
def test_chmod_mode_must_be_numeric(tools, mode):
    """Only an octal mode is passed on, as FirecREST doesn't escape it."""
    with pytest.raises(ToolError, match="is not a numeric mode"):
        tools.chmod("lumi", ALLOWED, mode)
    tools.client.chmod.assert_not_called()
