"""Tests for the tools with a mock client: that every tool checks its arguments, that
every tool works when it is called through FastMCP, and the behaviour of submit,
read_file, chgrp, upload and download.
"""

import asyncio

import pytest
from fastmcp import Client, FastMCP
from fastmcp.decorators import get_fastmcp_meta
from fastmcp.exceptions import ToolError
from firecrest.v2 import ExternalDownload, ExternalUpload

from firecrest_mcp.tools.compute import FirecrestComputeToolsMixin
from firecrest_mcp.tools.filesystem import FirecrestFilesystemToolsMixin
from firecrest_mcp.tools.status import FirecrestStatusToolsMixin

# Allowed and denied by the default CONFIG in conftest.py.
ALLOWED_REMOTE_PATH = "/scratch/project_1/x"
DENIED_REMOTE_PATH = "/etc/x"
ALLOWED_LOCAL_PATH = "data/x"
DENIED_LOCAL_PATH = "x"

# What the mock client's userinfo returns.
MOCK_USERINFO = {"user": {"name": "me"}}
# A job of that user. The job tools refuse a job of anyone else.
MOCK_OWN_JOB = {"jobId": "1", "user": "me"}

# What the mock client returns for each tool. A tool that is not listed returns an
# empty dict. None means that the client returns nothing.
MOCK_CLIENT_RESULTS = {
    "userinfo": MOCK_USERINFO,
    "systems": [{"name": "lumi"}],
    "partitions": [{"name": "small"}],
    "reservations": [{"name": "training"}],
    "list_files": [{"name": "x"}],
    "read_file": "text",
    "compress": None,
    "extract": None,
    "rm": None,
    "upload": None,
    "download": ExternalDownload(
        client=None,
        transfer_info={"transferJob": {"jobId": "2"}},
        file_path=ALLOWED_LOCAL_PATH,
    ),
    "job_info": [MOCK_OWN_JOB],
    "job_metadata": [{"jobId": "1", "script": "x"}],
}

# Each tool with its remote path arguments, local path arguments and its other
# arguments (besides system_name). Every path argument must be checked.
TOOLS_RESTRICTED = [
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

# Tools with no argument that the config restricts, with the same fields as
# TOOLS_RESTRICTED. test_every_tool_is_listed fails for a tool in neither list.
TOOLS_NOT_RESTRICTED = [
    ("systems", [], [], {}),
    ("partitions", [], [], {}),
    ("reservations", [], [], {}),
    ("userinfo", [], [], {}),
    ("job_info", [], [], {}),
    ("job_metadata", [], [], {"jobid": MOCK_OWN_JOB["jobId"]}),
    ("cancel_job", [], [], {"jobid": MOCK_OWN_JOB["jobId"]}),
    ("attach_to_job", [], [], {"jobid": MOCK_OWN_JOB["jobId"], "command": "hostname"}),
]

# Every tool. submit is listed twice, once for each kind of script path.
ALL_TOOLS = TOOLS_RESTRICTED + TOOLS_NOT_RESTRICTED

# Tools with an account argument, which defaults to default_account. job_info also
# has an account argument, but it only filters the jobs that job_info lists.
TOOLS_WITH_ACCOUNT = [
    tool
    for tool in TOOLS_RESTRICTED
    if tool[0]
    in {"mv", "compress", "extract", "cp", "rm", "upload", "download", "submit"}
]


def restricted_tool(name):
    """Return the first entry of TOOLS_RESTRICTED for a tool."""
    for tool in TOOLS_RESTRICTED:
        if tool[0] == name:
            return tool
    raise ValueError(f"{name} is not in TOOLS_RESTRICTED")


# The tools with a mock FirecREST client, so no real system is contacted. The mock
# has the client's signatures, so a call with a wrong argument name fails. Its
# methods return the values in MOCK_CLIENT_RESULTS.
class Tools(
    FirecrestComputeToolsMixin,
    FirecrestFilesystemToolsMixin,
    FirecrestStatusToolsMixin,
):
    def __init__(self, client):
        self.client = client
        for entry in ALL_TOOLS:
            name = entry[0]
            # A tool that is not in MOCK_CLIENT_RESULTS returns an empty dict.
            client_method(self, name).return_value = MOCK_CLIENT_RESULTS.get(name, {})


@pytest.fixture
def tools(config, tmp_path, mock_client):
    """Tools with the default config and an allowed local directory."""
    config()
    (tmp_path / "data").mkdir()
    return Tools(mock_client)


def arguments_with_default_paths(remote_args, local_args, other_args):
    """Return a tool's arguments with the default value for each path argument."""
    # A tool can have several path arguments, such as source_path and target_path
    # of mv. They all get the same path.
    remote_allowed = {argument: ALLOWED_REMOTE_PATH for argument in remote_args}
    local_allowed = {argument: ALLOWED_LOCAL_PATH for argument in local_args}
    return remote_allowed | local_allowed | other_args


def call(tools, name, remote_args, local_args, other_args, **overrides):
    """Call a tool's method directly, with the arguments in overrides replacing the
    default ones."""
    arguments = arguments_with_default_paths(remote_args, local_args, other_args)
    arguments.update(overrides)
    return getattr(tools, name)("lumi", **arguments)


def call_through_mcp(tools, name, arguments):
    """Call a tool the way an agent does: an MCP client sends the arguments to a
    FastMCP server. FastMCP checks them against the tool's parameter types and turns
    the tool's result into a response, which a direct call skips. If either step or
    the tool fails, this raises a ToolError."""
    server = FastMCP("test")
    server.add_tool(getattr(tools, name))

    # The client is async, so the call is put in a coroutine that asyncio runs.
    async def run():
        async with Client(server) as client:
            return await client.call_tool(name, arguments)

    return asyncio.run(run())


def client_method(tools, name):
    """Return the method of the mock client that a tool calls."""
    if name == "read_file":
        return tools.client.view
    if name == "chgrp":
        return tools.client.chown
    # Every other tool calls the client method of its own name.
    return getattr(tools.client, name)


def ids(entries):
    """Return a test ID for each entry: the tool name and its path arguments, so that
    the two submit entries get different IDs."""
    result = []
    for name, remote_args, local_args, other_args in entries:
        result.append("-".join([name] + remote_args + local_args))
    return result


def test_every_tool_is_listed():
    """A new tool must be added to TOOLS_RESTRICTED or to TOOLS_NOT_RESTRICTED. The
    tools are listed as server.py registers them: every public method with @tool()."""

    tools = set()
    for name in dir(Tools):
        # The same rule as the registration loop in server.py.
        if name.startswith("_"):
            continue
        if get_fastmcp_meta(getattr(Tools, name)) is not None:
            tools.add(name)
    assert tools == {tool[0] for tool in ALL_TOOLS}, (
        "Add a new tool to TOOLS_RESTRICTED, or to TOOLS_NOT_RESTRICTED if the config"
        " controls none of its arguments. Remove a deleted tool from them."
    )


@pytest.mark.parametrize(
    ("name", "remote_args", "local_args", "other_args"),
    TOOLS_RESTRICTED,
    ids=ids(TOOLS_RESTRICTED),
)
def test_tool_with_allowed_arguments_calls_client(
    tools, name, remote_args, local_args, other_args
):
    """Each tool calls the client when its arguments are allowed."""
    call(tools, name, remote_args, local_args, other_args)
    client_method(tools, name).assert_called_once()


@pytest.mark.parametrize(
    ("name", "remote_args", "local_args", "other_args"), ALL_TOOLS, ids=ids(ALL_TOOLS)
)
def test_tool_works_through_fastmcp(tools, name, remote_args, local_args, other_args):
    """Each tool can be called through FastMCP with its default arguments without an
    error."""
    arguments = arguments_with_default_paths(remote_args, local_args, other_args)
    # systems is the only tool without a system_name.
    if name != "systems":
        arguments["system_name"] = "lumi"
    call_through_mcp(tools, name, arguments)


# A system name with which pyfirecrest's userinfo requests the URL of the view
# endpoint for /etc/passwd.
TRAVERSAL_SYSTEM_NAME = "../filesystem/lumi/ops/view?path=/etc/passwd&x="


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("userinfo", {}),
        ("list_files", {"path": ALLOWED_REMOTE_PATH}),
        ("job_info", {}),
    ],
)
def test_system_name_pattern(tools, name, arguments):
    """A system name with characters other than letters, digits, '_' and '-' is
    refused before the client is called."""
    arguments["system_name"] = TRAVERSAL_SYSTEM_NAME
    with pytest.raises(ToolError, match="String should match pattern"):
        call_through_mcp(tools, name, arguments)
    client_method(tools, name).assert_not_called()


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("job_info", {}),
        ("job_metadata", {}),
        ("cancel_job", {}),
        ("attach_to_job", {"command": "hostname"}),
    ],
)
@pytest.mark.parametrize("jobid", ["../1", "1?x=", "1,2"])
def test_jobid_pattern(tools, name, arguments, jobid):
    """A job ID with characters other than letters and digits is refused before the
    client is called."""
    arguments["system_name"] = "lumi"
    arguments["jobid"] = jobid
    with pytest.raises(ToolError, match="String should match pattern"):
        call_through_mcp(tools, name, arguments)
    tools.client.job_info.assert_not_called()
    client_method(tools, name).assert_not_called()


def denied_case(tool, argument, value):
    """Return a case of the denied-argument test: the tool with one denied argument."""
    return pytest.param(*tool, {argument: value}, id=f"{tool[0]}-{argument}")


def denied_argument_cases():
    """Return a case for each argument that the config restricts, with a value that
    the config doesn't allow."""
    cases = []
    for tool in TOOLS_RESTRICTED:
        remote_args = tool[1]
        local_args = tool[2]
        for argument in remote_args:
            cases.append(denied_case(tool, argument, DENIED_REMOTE_PATH))
        for argument in local_args:
            cases.append(denied_case(tool, argument, DENIED_LOCAL_PATH))
    # The config lists no account, partition or reservation called x and no group
    # called other.
    for tool in TOOLS_WITH_ACCOUNT:
        cases.append(denied_case(tool, "account", "x"))
    cases.append(denied_case(restricted_tool("chgrp"), "group", "other"))
    cases.append(denied_case(restricted_tool("submit"), "partition", "x"))
    cases.append(denied_case(restricted_tool("submit"), "reservation", "x"))
    return cases


@pytest.mark.parametrize(
    ("name", "remote_args", "local_args", "other_args", "denied"),
    denied_argument_cases(),
)
def test_tool_with_denied_argument_does_not_call_client(
    tools, name, remote_args, local_args, other_args, denied
):
    """Any denied argument stops the tool before it calls the client."""
    with pytest.raises(ToolError, match="is not in"):
        call(tools, name, remote_args, local_args, other_args, **denied)
    assert not tools.client.method_calls


@pytest.mark.parametrize(
    ("name", "remote_args", "local_args", "other_args"),
    TOOLS_WITH_ACCOUNT,
    ids=ids(TOOLS_WITH_ACCOUNT),
)
def test_tool_uses_default_account(tools, name, remote_args, local_args, other_args):
    """A tool called without an account passes the default account as the client's
    account argument."""
    call(tools, name, remote_args, local_args, other_args)
    assert client_method(tools, name).call_args.kwargs["account"] == "project_1"


@pytest.mark.parametrize(
    ("directory", "filename"),
    [
        # An absolute filename made posixpath.join drop the directory, so the quote
        # in it went unchecked into FirecREST's shell command.
        ("/etc/x'; id; '", "/scratch/project_1/f"),
        ("/scratch/project_1", "../project_2/f"),
        ("/scratch/project_1", "sub/f"),
        ("/scratch/project_1", ""),
    ],
)
def test_upload_filename_is_one_name(tools, directory, filename):
    """upload refuses a filename that is empty or contains '/'."""
    with pytest.raises(ToolError, match="must not be empty or contain '/'"):
        tools.upload("lumi", ALLOWED_LOCAL_PATH, directory, filename)
    tools.client.upload.assert_not_called()


# What FirecREST returns when it starts a transfer job: the job, and directives with
# signed URLs for moving the data.
TRANSFER_JOB = {"jobId": "2", "system": "lumi"}
TRANSFER_INFO = {
    "transferJob": TRANSFER_JOB,
    "transferDirectives": {"transferMethod": "s3", "downloadUrl": "https://s3/x"},
}


@pytest.mark.parametrize(
    ("name", "transfer", "arguments"),
    [
        (
            "upload",
            ExternalUpload(client=None, transfer_info=TRANSFER_INFO, local_file=None),
            {
                "system_name": "lumi",
                "local_file": ALLOWED_LOCAL_PATH,
                "directory": "/scratch/project_1",
                "filename": "f",
            },
        ),
        (
            "download",
            ExternalDownload(client=None, transfer_info=TRANSFER_INFO, file_path=None),
            {
                "system_name": "lumi",
                "source_path": ALLOWED_REMOTE_PATH,
                "target_path": ALLOWED_LOCAL_PATH,
            },
        ),
    ],
    ids=["upload", "download"],
)
def test_transfer_returns_only_the_job(tools, name, transfer, arguments):
    """upload and download return the transfer job without the signed URLs."""
    client_method(tools, name).return_value = transfer
    result = call_through_mcp(tools, name, arguments)
    assert result.data == TRANSFER_JOB


@pytest.mark.parametrize(
    ("name", "remote_args", "local_args", "other_args"),
    [
        ("upload", ["directory"], ["local_file"], {"filename": "f"}),
        ("download", ["source_path"], ["target_path"], {}),
    ],
    ids=["upload", "download"],
)
def test_transfer_waits_for_the_data(tools, name, remote_args, local_args, other_args):
    """upload and download always wait for the transfer job, because only then is the
    data moved."""
    call(tools, name, remote_args, local_args, other_args)
    assert client_method(tools, name).call_args.kwargs["blocking"] is True
    # The agent can't ask for a transfer that doesn't wait.
    arguments = arguments_with_default_paths(remote_args, local_args, other_args)
    arguments["system_name"] = "lumi"
    arguments["blocking"] = False
    with pytest.raises(ToolError, match="Unexpected keyword argument"):
        call_through_mcp(tools, name, arguments)


def submit(tools, script, **job_options):
    """Submit a script and return the keyword arguments the client was called with."""
    tools.submit("lumi", ALLOWED_REMOTE_PATH, script_str=script, **job_options)
    return tools.client.submit.call_args.kwargs


@pytest.mark.parametrize(
    (
        "job_options",
        "expected_account",
        "expected_partition",
        "expected_reservation",
    ),
    [
        # Without job options, a job gets the default account and partition.
        ({}, "project_1", "small", None),
        (
            {"account": "project_2", "partition": "debug", "reservation": "training"},
            "project_2",
            "debug",
            "training",
        ),
        # A comma-separated list is allowed if every item in it is listed.
        ({"partition": "small,debug"}, "project_1", "small,debug", None),
    ],
)
def test_submit_options(
    tools, job_options, expected_account, expected_partition, expected_reservation
):
    """The client gets the job's account, partition and reservation."""
    client_call = submit(tools, "#!/bin/bash", **job_options)
    assert client_call["account"] == expected_account
    assert client_call["partition"] == expected_partition
    assert client_call["reservation"] == expected_reservation


def test_submit_overrides_script(tools):
    """The script's #SBATCH lines aren't checked, and the default account and
    partition are passed even when the script sets its own. FirecREST passes them to
    sbatch as --account and --partition, which take precedence over #SBATCH lines."""
    client_call = submit(tools, "#SBATCH -A project_3 -p standard\n")
    assert client_call["account"] == "project_1"
    assert client_call["partition"] == "small"


@pytest.mark.parametrize(
    ("job_options", "error"),
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
def test_submit_denied(tools, job_options, error):
    """Denied arguments stop the job."""
    with pytest.raises(ToolError, match=error):
        submit(tools, "#!/bin/bash\n", **job_options)
    tools.client.submit.assert_not_called()


def test_submit_needs_exactly_one_script(tools):
    """Exactly one of the three script arguments must be given."""
    with pytest.raises(ToolError, match="Exactly one"):
        tools.submit("lumi", ALLOWED_REMOTE_PATH)
    with pytest.raises(ToolError, match="Exactly one"):
        tools.submit(
            "lumi",
            ALLOWED_REMOTE_PATH,
            script_str="x",
            script_local_path=ALLOWED_LOCAL_PATH,
        )
    tools.client.submit.assert_not_called()


def test_submit_needs_working_dir(tools):
    """submit refuses a job without a working directory, which FirecREST requires."""
    arguments = {"system_name": "lumi", "working_dir": None, "script_str": "x"}
    with pytest.raises(ToolError, match="working_dir"):
        call_through_mcp(tools, "submit", arguments)
    tools.client.submit.assert_not_called()


def test_submit_without_default_partition(config, mock_client):
    """Without default_partition, a partition must be given as an argument."""
    config(
        "[lumi]\n"
        'remote_paths = ["/scratch/project_1"]\n'
        'accounts = ["p"]\n'
        'default_account = "p"\n'
        'partitions = ["small"]\n'
    )
    tools = Tools(mock_client)
    with pytest.raises(ToolError, match="No partition given"):
        tools.submit("lumi", ALLOWED_REMOTE_PATH, script_str="#SBATCH -p small")
    tools.submit(
        "lumi", ALLOWED_REMOTE_PATH, script_str="#!/bin/bash", partition="small"
    )
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
    assert tools.read_file("lumi", ALLOWED_REMOTE_PATH, **kwargs) == expected
    getattr(tools.client, method).assert_called_once()


def test_read_file_first_and_last_lines(tools):
    """Asking for both the first and the last lines is an error."""
    with pytest.raises(ToolError, match="at most one"):
        tools.read_file("lumi", ALLOWED_REMOTE_PATH, first_lines=1, last_lines=1)
    assert not tools.client.method_calls


def test_chgrp_keeps_owner(tools):
    """chgrp calls chown with an empty owner. That is the default of FirecREST's
    chown request, and FirecREST then changes only the group."""
    tools.chgrp("lumi", ALLOWED_REMOTE_PATH, "project_1")
    tools.client.chown.assert_called_once_with(
        "lumi", path=ALLOWED_REMOTE_PATH, owner="", group="project_1"
    )


def test_compress_has_no_match_pattern(tools):
    """match_pattern is never passed, as FirecREST puts it into a shell command
    without escaping it."""
    tools.compress("lumi", ALLOWED_REMOTE_PATH, ALLOWED_REMOTE_PATH)
    assert "match_pattern" not in tools.client.compress.call_args.kwargs


@pytest.mark.parametrize("mode", ["u+x", "700'; rm -rf ~; '", "7000a", "75", ""])
def test_chmod_mode_must_be_numeric(tools, mode):
    """Only an octal mode is passed on, as FirecREST doesn't escape it."""
    with pytest.raises(ToolError, match="is not a numeric mode"):
        tools.chmod("lumi", ALLOWED_REMOTE_PATH, mode)
    tools.client.chmod.assert_not_called()
