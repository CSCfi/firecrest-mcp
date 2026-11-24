"""Tools that don't use the FirecREST client."""

from fastmcp.tools import tool

from firecrest_mcp.config import (
    _local_path_entries,
    cluster_name,
    load_cluster_config,
)


@tool()
def show_config() -> dict:
    """Return the settings from .firecrest-mcp.toml that apply to this server:
    local_paths and this cluster's table. A key that is missing from the file is shown
    as [] or null and allows nothing. The file is read on every call."""
    return {
        "local_paths": _local_path_entries(),
        cluster_name(): load_cluster_config().model_dump(),
    }
