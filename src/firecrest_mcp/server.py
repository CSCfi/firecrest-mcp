"""The MCP server: the FirecREST client and the tools of one system, chosen by
FIRECREST_URL.
"""

import os
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.decorators import get_fastmcp_meta
from firecrest.v2 import Firecrest

from firecrest_mcp.auth import TokenAuth
from firecrest_mcp.config import active_config, cluster_name
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


url = os.getenv("FIRECREST_URL", None)
if not url:
    raise RuntimeError("Environment variable FIRECREST_URL is not defined.")

fc = FirecrestClientWrapper(url)

# Rules for the agent that every server sends, outside context/ because every file
# there is a cluster's.
GROUND_RULES = Path(__file__).parent / "ground_rules.md"
CONTEXT_DIR = Path(__file__).parent / "context"


def instructions_for(cluster: str) -> str:
    """Returns the ground rules, followed by context/<cluster>.md if there is one."""
    parts = [GROUND_RULES]
    context_file = CONTEXT_DIR / f"{cluster}.md"
    if context_file.exists():
        parts.append(context_file)
    return "\n".join(part.read_text() for part in parts)


mcp = FastMCP("FirecREST v2", instructions=instructions_for(cluster_name()))

# Only the public methods with @tool() are tools, as in FastMCP's own discovery of
# tools in a module.
for name in dir(fc):
    if name.startswith("_"):
        continue
    method = getattr(fc, name)
    if get_fastmcp_meta(method) is not None:
        mcp.add_tool(method)

# Tools that don't use the FirecREST client are registered here.
mcp.tool(active_config, name="config")
