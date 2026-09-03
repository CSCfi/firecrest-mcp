# FirecREST v2 MCP server

## Installation

```bash
git clone <repo-url> firecrest-mcp
pip install firecrest-mcp 
```

## Usage

Set the value of the `FIRECREST_TOKEN` environment variable to your FirecREST token.

```bash
export FIRECREST_TOKEN=<your-firecrest-token>
```

To use the server for interacting with LUMI using OpenCode, edit your `opencode.json` to include
the contents below.

```json
{
    "$schema": "https://opencode.ai/config.json",
    "mcp": {
        "firecrest-lumi": {
            "type": "local",
            "command": ["firecrest-mcp", "https://api.lumi.csc.fi/v1"],
            "enabled": true
        }
    }
}
```
