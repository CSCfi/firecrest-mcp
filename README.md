# FirecREST v2 MCP server

Lets an AI agent on your workstation, such as Claude Code or OpenCode, work on HPC
clusters through FirecREST: browse and transfer files, and submit and monitor Slurm
jobs. The agent runs locally and reaches the cluster only through this server's tools.
A config file limits what the tools can do (see [Config file](#config-file)).
[Safeguards](docs/safeguards.md) lists the ways the server limits the agent and what
it doesn't restrict.

The server is built for CSC's LUMI and Roihu, which get cluster-specific instructions
for the agent. Other clusters with a FirecREST v2 API should work without them, and can
be given their own (see [Other clusters](#other-clusters)). For LUMI and Roihu, also add
the documentation servers run by CSC and the LUMI AI Factory (see
[Documentation servers](#documentation-servers)).

## Installation

Install the server as a [uv](https://docs.astral.sh/uv/) tool:

```bash
uv tool install git+https://github.com/CSCfi/firecrest-mcp.git
```

To update the server to the latest commit, run `uv tool upgrade firecrest-mcp`.

## Setup

Get a FirecREST token (for LUMI and Roihu, see
[CSC's documentation](https://docs.csc.fi/computing/firecrest/)) and save it
in a plain text file at `~/.firecrest-token`. The file must be readable only by you, or
the server won't use it. The server reads the token for each request, so you can refresh
it by overwriting the file.

```bash
touch ~/.firecrest-token
chmod 600 ~/.firecrest-token
nano ~/.firecrest-token   # or any text editor: paste the token and save
```

Each local project you use with FirecREST gets its own config file,
`.firecrest-mcp.toml`, which limits what the agent working in that project can do on the
clusters. Download the example config into the project directory:

```bash
curl -o .firecrest-mcp.toml \
  https://raw.githubusercontent.com/CSCfi/firecrest-mcp/main/examples/firecrest-mcp.toml
```

Then edit it (see [Config file](#config-file)). The server reads it on every call, so
changes take effect without restarting the agent. The server looks for the config in the
directory it starts in, which depends on how it runs. To keep the config outside the
project, start the server with `--config` and the file's path. The server then ignores
`.firecrest-mcp.toml` in the project, and relative `local_paths` entries still start
from the directory the server starts in.

## Connecting

The server uses stdio by default, and the agent starts the server from its MCP
configuration. We strongly recommend running the agent in a container instead, so that
it can only reach the files you mount into it, and not your FirecREST token or other
credentials. The agent then connects over HTTP to a server you start outside the
container.

### stdio

Add the server to your agent's global MCP configuration once for each cluster you want
to use. This makes it available wherever you start the agent.
`examples/claude-code/mcp-stdio.json` has entries for LUMI and Roihu that you can add to
your Claude Code configuration. They start the server with `firecrest-mcp`, which runs
the version installed with `uv tool install`. The file uses Claude Code's format.
Other agents use similar fields, often the same `command`, `args` and `env`, so adapt
the entries to your agent's MCP configuration.

Start the agent from the project directory, because the server starts there too and
reads the project's config there.

To keep the token somewhere else, add `--token-file` and its path to each server's
arguments in your MCP configuration. In Claude Code:

```json
"args": [
  "--firecrest-url", "https://api.lumi.csc.fi/v1",
  "--token-file", "~/secrets/firecrest-token"
]
```

### HTTP

If the agent runs in a container, start the server outside the container from the
project directory, and let the agent connect to it over HTTP. The token then stays
outside the container. [Connecting over HTTP](docs/http.md) gives the commands for the
server, Podman and the agent.

## Documentation servers

This server's instructions cover only the basics of each cluster, so for modules,
software or quotas the agent relies on its training, which may be out of date. CSC and
the LUMI AI Factory run public MCP servers that let the agent search their current
documentation. They need no token. Add them to your agent's global MCP configuration
next to this server.

| Server | Searches | Endpoint |
|---|---|---|
| [CSC Documentation MCP server](https://docs.csc.fi/computing/ai-tools/docs-mcp/) | CSC's user guide, which covers Roihu | `https://mcp.docs.csc.fi` |
| [LUMI AI Factory MCP server](https://docs.lumi-supercomputer.eu/laif/software/agent-infrastructure/#mcp-server) | LUMI's documentation and AI guide. It also reports LUMI's service status. | `https://lumi-aif-agents.2.rahtiapp.fi/mcp` |

In Claude Code:

```bash
claude mcp add --scope user --transport http csc-docs https://mcp.docs.csc.fi
claude mcp add --scope user --transport http lumi-aif https://lumi-aif-agents.2.rahtiapp.fi/mcp
```

## Config file

Tools only accept what the config file allows: `.firecrest-mcp.toml` in the project,
or the file that `--config` names. A missing file or key allows none of the operations
it controls, and unknown keys are errors. Each
cluster has a table named after its `--firecrest-url` host (`api.roihu.csc.fi` is
`[roihu]`), and the table covers all of the cluster's FirecREST systems (`cpu` and `gpu`
on Roihu, `lumi` on LUMI). See `examples/firecrest-mcp.toml` for every key, and
[Safeguards](docs/safeguards.md) for how the server applies them.

Status tools, and job tools other than the `submit` tool, work without a config, since
they only read the cluster's status or act on your own jobs, with no paths or accounts
to check.

The `show_config` tool shows the agent the parts of the config that its server applies:
`local_paths` and the cluster's table, with every key. It fails, like the other tools,
when the config is missing or invalid.

The file tools for copying, moving, deleting, compressing, extracting, uploading and
downloading need an account, because they may run a transfer job, a Slurm job that
FirecREST starts for large or slow file operations. The account is required even if no
transfer job runs. The agent can name the account when it calls the tool, or you can set
`default_account` in the config so that it doesn't have to.

The `groups` key lists the groups that the `chgrp` tool may set on a file. This lets the
agent share a file you moved into a project directory with the project's members.

### Risks

**Don't list your home directory or other places with credentials, such as `~/.ssh`, in
`local_paths`.** The server protects only its own config file, the token file and the
project's `.git/`. It can't know where else you keep secrets or which files run code,
so the agent can send anything else in `local_paths` to the cluster and overwrite it
with `download`.

**The `submit` tool doesn't check the job script.** Its commands run with all of your
permissions, including outside `remote_paths`.

### Agent permissions

The agent could widen its own access by editing `.firecrest-mcp.toml`, or read your
token, with its own tools. The server's instructions tell it not to, which stops an
agent that follows them, but not one that ignores them, for example after a prompt
injection. An agent in a container can't reach a config outside the project that the
server reads with `--config`, as [Connecting over HTTP](docs/http.md) describes.
Otherwise, if your agent has permission settings, use them to deny it writes to the
config and reads of the token file. In Claude Code, for example, add these keys to
`~/.claude/settings.json`, merged with what is already there, and start a new session:

```json
{
  "permissions": {
    "deny": ["Edit(.firecrest-mcp.toml)", "Read(~/.firecrest-token)"]
  },
  "sandbox": {
    "filesystem": {
      "denyWrite": ["//**/.firecrest-mcp.toml"],
      "denyRead": ["~/.firecrest-token"]
    }
  }
}
```

The `Edit` rule stops the Edit and Write tools from changing the config in any project,
and the `Read` rule stops the Read tool from reading the token. The sandbox entries stop
Bash commands from doing either, but only where the
[sandbox](https://code.claude.com/docs/en/sandboxing) is turned on. If you start the
server with `--token-file`, use that path instead. This makes it harder for the agent,
not impossible.

## Other clusters

The server should work with any cluster that has a FirecREST v2 API, though it has only
been used on LUMI and Roihu. The `--firecrest-url` option, set in the server's entry in
your MCP configuration, points the server at a cluster's API, and the server won't
start without it. To adapt the server to another cluster:

- Add a server entry for the cluster to your MCP configuration, with its
  `--firecrest-url`. The server names the cluster after the first part of the API's host
  name other than `api`, and uses that name for the cluster's table in the config file.
  For example, `https://api.hpc.example.org/v1` is the cluster `hpc`, with the table
  `[hpc]`.
- Optionally, in a clone of the repo, add
  `src/firecrest_mcp/context/clusters/<cluster name>.md` (e.g. `hpc.md`) with
  instructions for the agent, such as where its documentation is and what the agent
  should know before it looks there (see `lumi.md`). Then install the server from the
  clone with `uv tool install --reinstall .`. A file with any other name is ignored
  without a warning. Start the file with a `###` header naming the cluster. The server
  sends it after its shared context for all clusters, in
  `src/firecrest_mcp/context/shared.md`.
- If a directory has two names, as `/project` and `/projappl` do on LUMI, add it to
  `PATH_ALIASES` in `src/firecrest_mcp/config.py`.

## Development

The repo is set up as a project of its own, with a `.firecrest-mcp.toml` in the repo
root that git ignores. To run the checked-out code, copy
`dev/mcp-stdio.json` or `dev/mcp-http.json` to `.mcp.json` in the repo root, which
git also ignores. Their servers are named `firecrest-lumi-dev` and
`firecrest-roihu-dev`, so they don't clash with servers you installed for normal use.

- `mcp-stdio.json` starts the server with `uv run firecrest-mcp`.
  Restart Claude Code after switching branches or editing the code.
- `mcp-http.json` connects to servers on ports 8000 and 8001. Start
  them from the repo root with `uv run firecrest-mcp -u <URL> -t http`, as
  [Connecting over HTTP](docs/http.md) describes, and restart them after switching
  branches or editing the code.

Install the pre-commit hooks, which run `ruff check`, `ruff format --check`,
`ty check` and `pytest` before each commit:

```bash
uv run pre-commit install
```
