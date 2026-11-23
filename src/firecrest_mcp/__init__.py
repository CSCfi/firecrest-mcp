"""An MCP server that exposes file and Slurm operations on HPC systems through
FirecREST.
"""

import argparse
import logging
import sys

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
        "127.0.0.1, localhost, ::1 and the --host address (may be repeated)",
    )
    parser.add_argument(
        "--log-level",
        type=str.upper,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="WARNING",
    )
    args = parser.parse_args(argv)

    if args.transport == "stdio" and (
        args.host is not None or args.port is not None or args.allowed_host
    ):
        parser.error("--host, --port and --allowed-host need --transport http")

    logging.basicConfig(level=args.log_level)

    try:
        run_server(args.transport, args.host, args.port, args.allowed_host)
    except KeyboardInterrupt:
        # Ctrl-C stops the server without a traceback. 130 is the shell's exit status
        # for a process stopped by SIGINT.
        sys.exit(130)


def run_server(
    transport: str, host: str | None, port: int | None, allowed_hosts: list[str]
) -> None:
    """Import the server and run it until it stops."""
    # Imported here because server.py needs FIRECREST_URL, and --help and option
    # errors should work without it.
    from firecrest_mcp.server import mcp

    if transport == "stdio":
        mcp.run(transport="stdio", show_banner=False)
        return
    # The Host check stops a web page in the user's browser from reaching the server
    # through DNS rebinding.
    mcp.run(
        transport="http",
        host=DEFAULT_HOST if host is None else host,
        port=DEFAULT_PORT if port is None else port,
        host_origin_protection=True,
        allowed_hosts=allowed_hosts,
        show_banner=False,
    )
