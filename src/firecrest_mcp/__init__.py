"""An MCP server that exposes file and Slurm operations on HPC systems through
FirecREST.
"""


def main() -> None:
    """Run the server."""
    from firecrest_mcp.server import mcp

    mcp.run()
