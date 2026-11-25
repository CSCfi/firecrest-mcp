"""The MCP server: the FirecREST client and the tools of one cluster, chosen by
--firecrest-url.
"""

import sys
from pathlib import Path

import httpx
import mcp_types
from fastmcp import FastMCP
from fastmcp.decorators import get_fastmcp_meta
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools.base import ToolResult
from firecrest.v2 import Firecrest

from firecrest_mcp import settings
from firecrest_mcp.auth import TokenAuth
from firecrest_mcp.config import cluster_name
from firecrest_mcp.metadata import get_server_metadata, get_update_message
from firecrest_mcp.tools.clientless import show_config
from firecrest_mcp.tools.compute import FirecrestComputeToolsMixin
from firecrest_mcp.tools.filesystem import FirecrestFilesystemToolsMixin
from firecrest_mcp.tools.status import FirecrestStatusToolsMixin

# How long to wait for a connection to FirecREST, in seconds. A request has no time
# limit once it is connected, so that large direct transfers aren't cut off.
CONNECT_TIMEOUT = 10


class FirecrestClientWrapper(
    FirecrestComputeToolsMixin,
    FirecrestFilesystemToolsMixin,
    FirecrestStatusToolsMixin,
):
    def __init__(self, url: str):
        self.client = Firecrest(
            firecrest_url=url,
            authorization=TokenAuth(),
        )
        # pyfirecrest waits forever by default, so a host that never answers, such as
        # one from a wrong --firecrest-url, would make every tool hang.
        self.client.timeout = httpx.Timeout(
            connect=CONNECT_TIMEOUT, read=None, write=None, pool=None
        )


class ConnectionErrorMiddleware(Middleware):
    """Replace the error of a tool call that couldn't connect to FirecREST with one
    that names the URL."""

    async def on_call_tool(
        self,
        context: MiddlewareContext[mcp_types.CallToolRequestParams],
        call_next: CallNext[mcp_types.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        try:
            return await call_next(context)
        except ToolError as e:
            # FastMCP turns a tool's exception into a ToolError whose cause is the
            # exception. For a connect timeout its text is "Upstream request timed
            # out, please retry", which doesn't say what is wrong.
            url = settings.firecrest_url
            if isinstance(e.__cause__, httpx.ConnectTimeout):
                raise ToolError(
                    f"Could not connect to FirecREST at {url} within"
                    f" {CONNECT_TIMEOUT} seconds. Check --firecrest-url."
                ) from None
            if isinstance(e.__cause__, httpx.ConnectError):
                raise ToolError(
                    f"Could not connect to FirecREST at {url}: {e.__cause__}."
                    " Check --firecrest-url."
                ) from None
            raise


# main() sets the URL before it imports this module.
if not settings.firecrest_url:
    raise RuntimeError("No --firecrest-url given.")

fc = FirecrestClientWrapper(settings.firecrest_url)


server_metadata = get_server_metadata()
update_message = get_update_message(
    server_metadata.local_version, server_metadata.upstream_version
)
if update_message:
    print(update_message, file=sys.stderr)

CONTEXT_DIR = Path(__file__).parent / "context"
SHARED_CONTEXT = CONTEXT_DIR / "shared.md"
CLUSTER_DIR = CONTEXT_DIR / "clusters"


def instructions_for(cluster: str) -> str:
    """Returns the shared context, followed by the cluster's context if it exists."""
    parts = []

    if update_message:
        parts.append(update_message)

    parts.append(SHARED_CONTEXT.read_text())

    cluster_file = CLUSTER_DIR / f"{cluster}.md"
    if cluster_file.exists():
        parts.append(cluster_file.read_text())

    return "\n".join(parts)


mcp = FastMCP(
    "FirecREST v2",
    version=str(server_metadata.local_version),
    website_url=server_metadata.github_url,
    instructions=instructions_for(cluster_name()),
)

# Only the public methods with @tool() are tools, as in FastMCP's own discovery of
# tools in a module.
for name in dir(fc):
    if name.startswith("_"):
        continue
    method = getattr(fc, name)
    if get_fastmcp_meta(method) is not None:
        mcp.add_tool(method)

# Tools that don't use the FirecREST client are registered here.
mcp.add_tool(show_config)

mcp.add_middleware(ConnectionErrorMiddleware())
