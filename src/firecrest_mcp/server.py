"""The MCP server: the FirecREST client and the tools of one cluster, chosen by
--firecrest-url.
"""

import sys
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.decorators import get_fastmcp_meta
from firecrest.v2 import Firecrest

from firecrest_mcp import settings
from firecrest_mcp.auth import TokenAuth
from firecrest_mcp.config import cluster_name
from firecrest_mcp.metadata import get_server_metadata, get_update_message
from firecrest_mcp.tools.clientless import show_config
from firecrest_mcp.tools.compute import FirecrestComputeToolsMixin
from firecrest_mcp.tools.filesystem import FirecrestFilesystemToolsMixin
from firecrest_mcp.tools.status import FirecrestStatusToolsMixin


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
