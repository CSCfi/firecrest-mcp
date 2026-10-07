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

The fastest way to try out the server is by running `opencode` in this directory, as the
`opencode.json` file included in this directory configures the MCP server locally. To
use the server outside of this directory, simply copy the contents of the included
`opencode.json` file to your global config (`~/.config/opencode/opencode.json`).

The server also requires the `FIRECREST_URL` environment variable, which points it at the
FirecREST API of the target system (e.g. `https://api.lumi.csc.fi/v1`). The included
`opencode.json` already sets it for LUMI and Roihu; if you configure the server some
other way, you must set it yourself, or the server will refuse to start.
