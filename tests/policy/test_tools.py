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
        self.client.view.return_value = "#!/bin/bash\n"


@pytest.fixture
def tools(config, tmp_path):
    """Tools with the default config and an allowed local job script."""
    config()
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "x").write_text("#!/bin/bash\n")
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
    ("script", "options"),
    [
        # Without a working directory or remote script, a job is not blocked, and it
        # gets the default account and partition.
        ("#!/bin/bash", ("project_1", "small", None)),
        # Options set in the script are checked and left to the script.
        ("#SBATCH -A project_2 -p debug --reservation training", (None, None, None)),
    ],
)
def test_submit_options(tools, script, options):
    """The client gets the job's account, partition and reservation."""
    args = submit(tools, script)
    assert (args["account"], args["partition"], args["reservation"]) == options


@pytest.mark.parametrize(
    ("script", "kwargs", "error"),
    [
        ("#SBATCH -A project_3", {}, "Account 'project_3' is not in"),
        ("#SBATCH -p standard", {}, "Partition 'standard' is not in"),
        ("#SBATCH -p small,standard", {}, "Partition 'standard' is not in"),
        ("#SBATCH --reservation=other", {}, "Reservation 'other' is not in"),
        ("#SBATCH --chdir=/etc", {}, "Remote path '/etc' is not in"),
        ("#SBATCH -o /etc/out", {}, "Remote path '/etc/out' is not in"),
        ("#SBATCH -e ../project_2/err", {}, "must not contain '..'"),
        # A directive the parser can't read stops the job.
        ("#SBATCH -A", {}, "Job script: "),
        # Environment variables that set Slurm options, in any letter case.
        ("", {"env_vars": {"SBATCH_ACCOUNT": "x"}}, "could change job options"),
        ("", {"env_vars": {"slurm_partition": "x"}}, "could change job options"),
        # An empty argument is not left to FirecREST's or Slurm's default.
        ("", {"account": ""}, "is not in"),
        ("", {"partition": ""}, "is not in"),
        ("", {"reservation": ""}, "is not in"),
    ],
)
def test_submit_denied(tools, script, kwargs, error):
    """Denied directives, arguments and environment variables, and unreadable
    directives, stop the job."""
    with pytest.raises(ToolError, match=error):
        submit(
            tools,
            f"#!/bin/bash\n{script}\n",
            working_dir="/scratch/project_1",
            **kwargs,
        )
    tools.client.submit.assert_not_called()


def test_submit_relative_output(tools):
    """Relative output paths are resolved against the working directory."""
    submit(tools, "#SBATCH -o out\n", working_dir="/scratch/project_1")
    with pytest.raises(ToolError, match="needs a working directory"):
        submit(tools, "#SBATCH -o out\n")
    with pytest.raises(ToolError, match="is not in"):
        submit(tools, "#SBATCH -D /etc\n#SBATCH -o out\n")


def test_submit_remote_script_checked(tools):
    """A remote script is read and its directives are checked."""
    tools.client.view.return_value = "#SBATCH -A project_3\n"
    with pytest.raises(ToolError, match="Account 'project_3'"):
        tools.submit("lumi", None, script_remote_path=ALLOWED)
    tools.client.submit.assert_not_called()


def test_submit_sends_checked_script(tools):
    """The script that was checked is submitted as a string."""
    tools.submit("lumi", None, script_local_path=ALLOWED_LOCAL)
    args = client_args(tools, "submit")
    assert args["script_str"] == "#!/bin/bash\n"
    assert args["script_local_path"] is None
    assert args["script_remote_path"] is None


def test_submit_needs_exactly_one_script(tools):
    """Exactly one of the three script arguments must be given."""
    with pytest.raises(ToolError, match="Exactly one"):
        tools.submit("lumi", None)
    with pytest.raises(ToolError, match="Exactly one"):
        tools.submit("lumi", None, script_str="x", script_local_path=ALLOWED_LOCAL)
    tools.client.submit.assert_not_called()


def test_submit_without_default_partition(config):
    """Without default_partition, a partition must be given somewhere."""
    config('[lumi]\naccounts = ["p"]\ndefault_account = "p"\npartitions = ["small"]\n')
    tools = Tools()
    with pytest.raises(ToolError, match="No partition given"):
        tools.submit("lumi", None, script_str="#!/bin/bash")
    tools.submit("lumi", None, script_str="#SBATCH -p small")
    tools.client.submit.assert_called_once()


def test_submit_paths_use_lumi_alias(tools):
    """The /project alias also applies to paths in #SBATCH directives."""
    submit(tools, "#SBATCH -D /project/project_1\n#SBATCH -o out\n")
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


@pytest.mark.parametrize("mode", ["u+x", "700'; rm -rf ~; '", "7000a", "75", ""])
def test_chmod_mode_must_be_numeric(tools, mode):
    """Only an octal mode is passed on, as FirecREST doesn't escape it."""
    with pytest.raises(ToolError, match="is not a numeric mode"):
        tools.chmod("lumi", ALLOWED, mode)
    tools.client.chmod.assert_not_called()
