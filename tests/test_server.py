"""Tests for the tools that the server registers and the options of main()."""

import asyncio
import importlib
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest
import requests
from fastmcp import Client
from fastmcp.decorators import get_fastmcp_meta

from firecrest_mcp import main, metadata, settings
from firecrest_mcp.tools.compute import FirecrestComputeToolsMixin
from firecrest_mcp.tools.filesystem import FirecrestFilesystemToolsMixin
from firecrest_mcp.tools.status import FirecrestStatusToolsMixin

# Tools in tools/clientless.py, which server.py registers by name. None of them
# takes an argument that .firecrest-mcp.toml restricts.
CLIENTLESS_TOOLS = {"show_config"}


@pytest.fixture(autouse=True)
def no_github_request(monkeypatch):
    """Make the update check fail without a request when a test imports server.py."""
    get = Mock(side_effect=requests.ConnectionError("no requests in tests"))
    monkeypatch.setattr(metadata.requests, "get", get)


URL = "https://api.lumi.csc.fi/v1"


@pytest.fixture
def server(monkeypatch):
    """The server module, imported with the URL that server.py needs. The settings
    are restored after the test, also those that main() sets."""
    monkeypatch.setattr(settings, "firecrest_url", URL)
    monkeypatch.setattr(settings, "token_file", settings.token_file)
    monkeypatch.setattr(settings, "config_file", settings.config_file)
    return importlib.import_module("firecrest_mcp.server")


def test_registered_tools(server):
    """The server registers every tool of the three mixins, the CLIENTLESS_TOOLS
    and nothing else. The list of the mixins' tools is tested in
    tests/config/test_tools.py."""
    mixins = [
        FirecrestComputeToolsMixin,
        FirecrestFilesystemToolsMixin,
        FirecrestStatusToolsMixin,
    ]
    expected = set()
    for mixin in mixins:
        for name in dir(mixin):
            # The same rule as the registration loop in server.py.
            if name.startswith("_"):
                continue
            if get_fastmcp_meta(getattr(mixin, name)) is not None:
                expected.add(name)
    tools = asyncio.run(server.mcp.list_tools())
    assert {tool.name for tool in tools} == expected | CLIENTLESS_TOOLS, (
        "Add a new tool in tools/clientless.py to CLIENTLESS_TOOLS. If it takes an"
        " argument that .firecrest-mcp.toml restricts, check it with load_config()"
        " and test that a denied value is refused."
    )


def test_instructions(server):
    """The instructions start with the shared context, followed by the cluster's
    context if it has one."""
    rules = server.SHARED_CONTEXT.read_text()
    assert rules.startswith("### Ground rules\n")
    assert server.instructions_for("lumi") == "\n".join(
        [rules, (server.CLUSTER_DIR / "lumi.md").read_text()]
    )
    assert server.instructions_for("hpc") == rules


def test_context_headers(server):
    """Each cluster's context starts with a ### header, so that it nests under the
    client's header for the server."""
    for path in server.CLUSTER_DIR.glob("*.md"):
        assert path.read_text().startswith("### "), path.name


@pytest.fixture
def recorded_runs(server, monkeypatch):
    """Replaces mcp.run of the server and returns the keyword arguments of each call."""
    calls = []
    monkeypatch.setattr(server.mcp, "run", lambda **kwargs: calls.append(kwargs))
    return calls


def test_main_stdio(recorded_runs):
    """Without other options, the server runs over stdio."""
    main(["-u", URL])
    assert recorded_runs == [{"transport": "stdio", "show_banner": False}]


def test_main_http(recorded_runs):
    """Over HTTP the server checks the Host header and allows the listed host names."""
    main(["-u", URL, "-t", "http", "--allowed-host", "a", "--allowed-host", "b"])
    assert recorded_runs == [
        {
            "transport": "http",
            "host": "127.0.0.1",
            "port": 8000,
            "host_origin_protection": True,
            "allowed_hosts": ["a", "b"],
            "show_banner": False,
        }
    ]


def test_main_http_host_port(recorded_runs):
    """--host and --port set the address and port the server listens on."""
    main(["-u", URL, "--transport", "http", "--host", "::1", "--port", "9000"])
    assert recorded_runs[0]["host"] == "::1"
    assert recorded_runs[0]["port"] == 9000


@pytest.mark.parametrize(
    "options", [["--host", "::1"], ["--port", "9000"], ["--allowed-host", "a"]]
)
def test_main_stdio_rejects_http_options(recorded_runs, options):
    """The HTTP options are refused over stdio, where they would have no effect."""
    with pytest.raises(SystemExit):
        main(["-u", URL, *options])
    assert recorded_runs == []


def test_main_keyboard_interrupt(server, monkeypatch):
    """Ctrl-C while the server runs exits with status 130 and no traceback."""

    def interrupted_run(**kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(server.mcp, "run", interrupted_run)
    with pytest.raises(SystemExit) as exit_info:
        main(["-u", URL])
    assert exit_info.value.code == 130


def test_main_settings(recorded_runs, tmp_path):
    """The URL, token file and config file options set the settings, with "~"
    expanded."""
    main(["--firecrest-url", URL, "--token-file", "~/t", "--config", "~/c.toml"])
    assert settings.firecrest_url == URL
    assert settings.token_file == Path("~/t").expanduser()
    assert settings.config_file == Path("~/c.toml").expanduser()
    main(
        [
            "-u",
            "https://api.roihu.csc.fi/v1",
            "-c",
            "other.toml",
            "-t",
            "http",
            "-p",
            "9000",
        ]
    )
    assert settings.firecrest_url == "https://api.roihu.csc.fi/v1"
    assert settings.config_file == Path("other.toml")


def test_main_defaults(recorded_runs):
    """Without the options, the token is read from ~/.firecrest-token and the config
    from .firecrest-mcp.toml in the working directory."""
    main(["-u", URL])
    assert settings.token_file == Path("~/.firecrest-token").expanduser()
    assert settings.config_file == Path(".firecrest-mcp.toml")


def test_main_requires_url(recorded_runs):
    """The server doesn't start without --firecrest-url."""
    with pytest.raises(SystemExit):
        main([])
    assert recorded_runs == []


def test_connect_timeout(server):
    """The client gives up on connecting to FirecREST after CONNECT_TIMEOUT seconds,
    but waits for a response without a limit."""
    expected = httpx.Timeout(
        connect=server.CONNECT_TIMEOUT, read=None, write=None, pool=None
    )
    assert server.fc.client.timeout == expected


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (
            httpx.ConnectTimeout("timed out"),
            (
                f"Could not connect to FirecREST at {URL} within 10 seconds."
                " Check --firecrest-url."
            ),
        ),
        (
            httpx.ConnectError("Name or service not known"),
            (
                f"Could not connect to FirecREST at {URL}: Name or service not known."
                " Check --firecrest-url."
            ),
        ),
        (RuntimeError("other"), "Error calling tool 'systems': other"),
    ],
)
def test_connection_errors_name_url(server, monkeypatch, error, message):
    """A tool that can't connect to FirecREST returns an error that names the URL.
    Other errors are left as FastMCP reports them."""
    monkeypatch.setattr(server.fc.client, "systems", Mock(side_effect=error))

    async def call_systems():
        async with Client(server.mcp) as client:
            return await client.call_tool("systems", {}, raise_on_error=False)

    result = asyncio.run(call_systems())
    assert result.is_error
    assert result.content[0].text == message
