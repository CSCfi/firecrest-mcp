"""Tools that don't use the FirecREST client."""

from fastmcp.tools import tool

from firecrest_mcp.config import cluster_name, load_config


@tool()
def show_config() -> dict:
    """Return the settings from the config file that apply to this server:
    local_paths and this cluster's table. A key that is missing from the file is shown
    as [] or null and allows nothing. The file is read on every call."""
    config = load_config()
    return {
        "local_paths": config.local_paths,
        cluster_name(): config.model_dump(exclude={"local_paths"}),
    }
