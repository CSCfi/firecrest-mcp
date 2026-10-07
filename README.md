# FirecREST v2 MCP server

## Installation

```bash
git clone <repo-url>
cd firecrest-mcp
uv tool install .
```

## Usage

Set the value of the `FIRECREST_TOKEN` environment variable to your FirecREST token.

```bash
export FIRECREST_TOKEN=<your-firecrest-token>
```

The fastest way to try out the server is by running `opencode` in this directory, as the
`opencode.json` file included in this directory configures the MCP server locally. To
use the server outside of this directory, simply copy the contents of the included
`opencode.json` file to your global config (`~/.config/opencode/opencode.json`).

The server also requires the `FIRECREST_URL` environment variable, which points it at the
FirecREST API of the target system (e.g. `https://api.lumi.csc.fi/v1`). The included
`opencode.json` already sets it for LUMI and Roihu; if you configure the server some
other way, you must set it yourself, or the server will refuse to start.
