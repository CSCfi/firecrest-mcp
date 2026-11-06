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
FIRECREST_URL=https://api.lumi.csc.fi/v1 firecrest-mcp --transport http --allowed-host host-loopback
```

The server runs until you stop it with Ctrl+C. To use a second cluster, start another
server in another terminal with `--port 8001`, because the first one uses port 8000.

To keep the token somewhere else, set `FIRECREST_TOKEN_PATH` in the same way as
`FIRECREST_URL`.

## Starting the container

The upload, download and submit tools use paths outside the container. Mount the
project into the container at the same path, so that a path the agent gives the server
means the same file on both sides.

The server listens only on `127.0.0.1`, so any process on the workstation can connect
to the port and use the tools with your token, within the limits of the config. Don't
set `--host 0.0.0.0` to let the container in, because other machines could then do the
same. The next paragraph shows how the container reaches `127.0.0.1` instead.

A container can't reach the workstation's `127.0.0.1` by default. Give the container an
address that leads there, under the name `host-loopback`. How to do that depends on the
container runtime. For example, with Podman:

```bash
podman run --network pasta:--map-host-loopback,169.254.1.3 \
  --add-host host-loopback:169.254.1.3 \
  <other options> <image> <agent command>
```

Here `--network` makes `169.254.1.3` in the container lead to the workstation's
`127.0.0.1`, and `--add-host` names that address `host-loopback`.

The server rejects a request if its `Host` header is not `127.0.0.1`, `localhost`,
`::1` or a name given with `--allowed-host`. Without this check, a web page open in your
browser could use DNS rebinding to reach the server and call its tools, for example to
submit a job. The container connects to `host-loopback`, so it sends that name as the
`Host` header, which `--allowed-host host-loopback` allows.

## Configuring the agent

In the container, add the server to the agent's MCP configuration. For example, in
Claude Code:

```json
{
  "mcpServers": {
    "firecrest-lumi": {
      "type": "http",
      "url": "http://host-loopback:8000/mcp"
    }
  }
}
```

For a second server, add another entry with its port in the URL. In OpenCode, the entry
has `"type": "remote"` and the same `url`.
