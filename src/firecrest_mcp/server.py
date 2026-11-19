"""The MCP server: the FirecREST client and the tools of one system, chosen by
FIRECREST_URL.
"""

import logging
import os
import sys
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.decorators import get_fastmcp_meta
from firecrest.v2 import Firecrest
from packaging.version import Version

from firecrest_mcp.auth import TokenAuth
from firecrest_mcp.config import active_config, cluster_name
from firecrest_mcp.metadata import get_server_metadata
from firecrest_mcp.tools.compute import FirecrestComputeToolsMixin
from firecrest_mcp.tools.filesystem import FirecrestFilesystemToolsMixin
from firecrest_mcp.tools.status import FirecrestStatusToolsMixin

logger = logging.getLogger(__name__)
logging.basicConfig()


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


def get_update_message(local_version: str, upstream_version: str | None) -> str | None:
    if not upstream_version:
        return
    if Version(local_version) < Version(upstream_version):
        return (
            "A newer version of FirecREST MCP is available. "
            "It is recommended to upgrade the package. "
            f"({local_version} -> {upstream_version})"
        )


local_version, upstream_version, website_url = get_server_metadata()
update_message = get_update_message(local_version, upstream_version)
if update_message:
    print(update_message, file=sys.stderr)

# Rules for the agent that every server sends, outside context/ because every file
# there is a cluster's.
GROUND_RULES = Path(__file__).parent / "ground_rules.md"
CONTEXT_DIR = Path(__file__).parent / "context"


def instructions_for(cluster: str) -> str:
    """Returns the ground rules, followed by context/<cluster>.md if there is one."""
    parts = []

    if update_message:
        parts.append(update_message)

    parts.append(GROUND_RULES.read_text())

    context_file = CONTEXT_DIR / f"{cluster}.md"
    if context_file.exists():
        parts.append(context_file.read_text())

    return "\n".join(parts)


mcp = FastMCP(
    "FirecREST v2",
    version=str(local_version),
    website_url=website_url,
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
mcp.tool(active_config, name="config")
