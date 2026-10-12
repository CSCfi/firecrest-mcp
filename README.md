# FirecREST v2 MCP server

## Installation

```bash
git clone <repo-url>
cd firecrest-mcp
uv tool install .
```

## Usage

Save your FirecREST token in a plain text file at `~/.firecrest/token`. The file must
not be accessible by other users, otherwise the server refuses to read it. The file is
read on every request, so the token can be refreshed by rewriting the file without
restarting the server.

```bash
mkdir -p ~/.firecrest
echo "<your-firecrest-token>" > ~/.firecrest/token
chmod 600 ~/.firecrest/token
```

To keep the token somewhere else, set the `FIRECREST_TOKEN_PATH` environment variable
to the path of the token file.

The server also requires the `FIRECREST_URL` environment variable, which points it at
the FirecREST API of the target system (e.g. `https://api.lumi.csc.fi/v1`). If it isn't
set, the server won't start.

### Client configuration

`examples/` has Claude Code and OpenCode configs for LUMI and Roihu. They start the
server with `uvx firecrest-mcp`, which runs the version installed with
`uv tool install .`. Run `uv tool install --reinstall .` after pulling to update it.

## Development

`.mcp.json` in the repo root starts the server with `uv run`, which uses the checked-out
code. Restart Claude Code after switching branches or editing the code.
