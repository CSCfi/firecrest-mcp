"""Tests of the tools that the server registers."""

import asyncio
import importlib

from firecrest_mcp.tools.compute import FirecrestComputeToolsMixin
from firecrest_mcp.tools.filesystem import FirecrestFilesystemToolsMixin
from firecrest_mcp.tools.status import FirecrestStatusToolsMixin


def test_registered_tools(monkeypatch):
    """The server registers every tool of the three mixins and nothing else. The
    list of tools itself is tested in tests/policy/test_tools.py."""
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
    assert {tool.name for tool in tools} == expected
