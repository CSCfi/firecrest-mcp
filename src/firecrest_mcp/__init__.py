"""An MCP server that exposes file and Slurm operations on HPC systems through
FirecREST.
"""

import argparse

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def main(argv: list[str] | None = None) -> None:
    """Run the server over stdio, or over HTTP for an agent in a container on the
    same workstation.
    """
    parser = argparse.ArgumentParser(prog="firecrest-mcp", description=main.__doc__)
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument(
        "--host", help=f"address to listen on over HTTP (default: {DEFAULT_HOST})"
    )
    parser.add_argument(
        "--port",
        type=int,
        help=f"port to listen on over HTTP (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--allowed-host",
        action="append",
        default=[],
        help="host name that clients may send in the Host header over HTTP, besides "
        "127.0.0.1, localhost and ::1 (may be repeated)",
    )
    args = parser.parse_args(argv)
    if args.transport == "stdio" and (
        args.host is not None or args.port is not None or args.allowed_host
    ):
        parser.error("--host, --port and --allowed-host need --transport http")

    from firecrest_mcp.server import mcp

    if args.transport == "stdio":
        mcp.run(transport="stdio")
        return
    # The Host check stops a web page in the user's browser from reaching the server
    # through DNS rebinding.
    mcp.run(
        transport="http",
        host=DEFAULT_HOST if args.host is None else args.host,
        port=DEFAULT_PORT if args.port is None else args.port,
        host_origin_protection=True,
        allowed_hosts=args.allowed_host,
    )
