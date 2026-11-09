"""Tests for the tools that the server registers and the options of main()."""

import asyncio
import importlib

import pytest

from firecrest_mcp import main
from firecrest_mcp.tools.compute import FirecrestComputeToolsMixin
from firecrest_mcp.tools.filesystem import FirecrestFilesystemToolsMixin
from firecrest_mcp.tools.status import FirecrestStatusToolsMixin


def test_registered_tools(monkeypatch):
    """The server registers every tool of the three mixins, the config tool and
    nothing else. The list of the mixins' tools is tested in
    tests/config/test_tools.py."""
    mixins = [
        FirecrestComputeToolsMixin,
        FirecrestFilesystemToolsMixin,
        FirecrestStatusToolsMixin,
    ]
    expected = {
        name
        for mixin in mixins
        for name in dir(mixin)
        if callable(getattr(mixin, name)) and not name.startswith("__")
    }
    # server.py reads FIRECREST_URL when it is imported.
    monkeypatch.setenv("FIRECREST_URL", "https://api.lumi.csc.fi/v1")
    server = importlib.import_module("firecrest_mcp.server")
    tools = asyncio.run(server.mcp.list_tools())
    assert {tool.name for tool in tools} == expected | {"config"}


@pytest.fixture
def run(monkeypatch):
    """Replaces mcp.run of the server and returns the keyword arguments of each call."""
    monkeypatch.setenv("FIRECREST_URL", "https://api.lumi.csc.fi/v1")
    server = importlib.import_module("firecrest_mcp.server")
    calls = []
    monkeypatch.setattr(server.mcp, "run", lambda **kwargs: calls.append(kwargs))
    return calls


def test_main_stdio(run):
    """Without options, the server runs over stdio."""
    main([])
    assert run == [{"transport": "stdio"}]


def test_main_http(run):
    """Over HTTP the server checks the Host header and allows the listed host names."""
    main(["--transport", "http", "--allowed-host", "a", "--allowed-host", "b"])
    assert run == [
        {
            "transport": "http",
            "host": "127.0.0.1",
            "port": 8000,
            "host_origin_protection": True,
            "allowed_hosts": ["a", "b"],
        }
    ]


def test_main_http_host_port(run):
    """--host and --port set the address and port the server listens on."""
    main(["--transport", "http", "--host", "::1", "--port", "9000"])
    assert run[0]["host"] == "::1"
    assert run[0]["port"] == 9000


@pytest.mark.parametrize(
    "options", [["--host", "::1"], ["--port", "9000"], ["--allowed-host", "a"]]
)
def test_main_stdio_rejects_http_options(run, options):
    """The HTTP options are refused over stdio, where they would have no effect."""
    with pytest.raises(SystemExit):
        main(options)
    assert run == []
