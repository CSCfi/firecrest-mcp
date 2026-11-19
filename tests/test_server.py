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


@pytest.fixture(autouse=True)
def no_github_request(monkeypatch):
    """Make the update check fail without a request when a test imports server.py."""
    get = Mock(side_effect=requests.ConnectionError("no requests in tests"))
    monkeypatch.setattr(metadata.requests, "get", get)


def test_registered_tools(monkeypatch):
    """The server registers every tool of the three mixins, the config tool and
    nothing else. The list of the mixins' tools is tested in
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
    # server.py reads FIRECREST_URL when it is imported.
    monkeypatch.setenv("FIRECREST_URL", "https://api.lumi.csc.fi/v1")
    server = importlib.import_module("firecrest_mcp.server")
    tools = asyncio.run(server.mcp.list_tools())
    assert {tool.name for tool in tools} == expected | {"config"}


def test_instructions(monkeypatch):
    """The instructions start with the ground rules, followed by the cluster's context
    if it has one."""
    monkeypatch.setenv("FIRECREST_URL", "https://api.lumi.csc.fi/v1")
    server = importlib.import_module("firecrest_mcp.server")
    rules = server.GROUND_RULES.read_text()
    assert rules.startswith("### Ground rules\n")
    assert server.instructions_for("lumi") == "\n".join(
        [rules, (server.CONTEXT_DIR / "lumi.md").read_text()]
    )
    assert server.instructions_for("hpc") == rules


def test_context_headers(monkeypatch):
    """Each cluster's context starts with a ### header, so that it nests under the
    client's header for the server."""
    monkeypatch.setenv("FIRECREST_URL", "https://api.lumi.csc.fi/v1")
    server = importlib.import_module("firecrest_mcp.server")
    for path in server.CONTEXT_DIR.glob("*.md"):
        assert path.read_text().startswith("### "), path.name


@pytest.fixture
def recorded_runs(monkeypatch):
    """Replaces mcp.run of the server and returns the keyword arguments of each call."""
    monkeypatch.setenv("FIRECREST_URL", "https://api.lumi.csc.fi/v1")
    server = importlib.import_module("firecrest_mcp.server")
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
