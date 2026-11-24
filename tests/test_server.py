"""Tests for the tools that the server registers and the options of main()."""

import asyncio
import importlib
from unittest.mock import Mock

import pytest
import requests
from fastmcp.decorators import get_fastmcp_meta

from firecrest_mcp import main, metadata
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


@pytest.fixture
def server(monkeypatch):
    """The server module, imported with the FIRECREST_URL that server.py needs."""
    monkeypatch.setenv("FIRECREST_URL", "https://api.lumi.csc.fi/v1")
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
    """Without options, the server runs over stdio."""
    main([])
    assert recorded_runs == [{"transport": "stdio", "show_banner": False}]


def test_main_http(recorded_runs):
    """Over HTTP the server checks the Host header and allows the listed host names."""
    main(["--transport", "http", "--allowed-host", "a", "--allowed-host", "b"])
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
    main(["--transport", "http", "--host", "::1", "--port", "9000"])
    assert recorded_runs[0]["host"] == "::1"
    assert recorded_runs[0]["port"] == 9000


@pytest.mark.parametrize(
    "options", [["--host", "::1"], ["--port", "9000"], ["--allowed-host", "a"]]
)
def test_main_stdio_rejects_http_options(recorded_runs, options):
    """The HTTP options are refused over stdio, where they would have no effect."""
    with pytest.raises(SystemExit):
        main(options)
    assert recorded_runs == []


def test_main_keyboard_interrupt(server, monkeypatch):
    """Ctrl-C while the server runs exits with status 130 and no traceback."""

    def interrupted_run(**kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(server.mcp, "run", interrupted_run)
    with pytest.raises(SystemExit) as exit_info:
        main([])
    assert exit_info.value.code == 130
