# Connecting over HTTP

If the agent runs in a container, the server can run outside the container instead, so
that the agent can't read your FirecREST token. The agent then connects to the server
over HTTP.

## Starting the server

Start the server outside the container, from the project directory, because the server
reads `.firecrest-mcp.toml` from the directory it starts in. `FIRECREST_URL` selects the
cluster: `https://api.lumi.csc.fi/v1` for LUMI or
`https://api.roihu.csc.fi/v1` for Roihu. For example, for LUMI:

```bash
cd path/to/project
FIRECREST_URL=https://api.lumi.csc.fi/v1 firecrest-mcp --transport http
```

The server runs until you stop it with Ctrl+C. To use a second cluster, start another
server in another terminal with `--port 8001`, because the first one uses port 8000.

To keep the token somewhere else, set `FIRECREST_TOKEN_PATH` in the same way as
`FIRECREST_URL`.

## Starting the container

The upload, download and submit tools use paths outside the container. Mount the
project into the container at the same path, so that a path the agent gives the server
means the same file on both sides.

The server listens only on `127.0.0.1` and doesn't ask for a password or key. Any
process on the workstation can connect to the port and use the tools with your token,
including the processes of other users on a shared machine. The config limits most
tools, but `submit` and `attach_to_job` run any command on the cluster as you.

A container can't reach the workstation's `127.0.0.1` by default. Don't set
`--host 0.0.0.0` to let the container in, because other machines could then do the
same. Instead, forward the server's port from the container's `127.0.0.1` to the
workstation's. How to do that depends on the container runtime. For example, with
Podman:

```bash
podman run --network pasta:-T,8000 <other options> <image> <agent command>
```

For two servers on ports 8000 and 8001, use `-T,8000-8001`. The forwarded port is
taken inside the container as well, so if a program there needs it, start the server
with another `--port` and forward that port.

The server rejects a request whose `Host` header is not `127.0.0.1`, `localhost`,
`::1`, the `--host` address or a name given with `--allowed-host`. This stops a web page
in your browser from reaching the server through DNS rebinding. The agent sends the
host from its URL, which is `127.0.0.1` with the forwarded port. If your setup gives the
agent another name or address, such as `host.docker.internal`, add it with
`--allowed-host`.

## Configuring the agent

In the container, add the server to the agent's MCP configuration. For example, in
Claude Code:

```json
{
  "mcpServers": {
    "firecrest-lumi": {
      "type": "http",
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

Write `127.0.0.1` and not `localhost`. The agent may try `localhost` as the IPv6
address `::1` first, and then the connection fails because the server listens only on
IPv4.

For a second server, add another entry with its port in the URL.
`examples/claude-code/mcp-http.json` has entries for LUMI on port 8000 and Roihu on port
8001. The file uses Claude Code's format. Other agents use similar fields, so adapt the
entries to your agent's MCP configuration.
