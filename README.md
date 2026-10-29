# FirecREST v2 MCP server

Lets an AI agent on your workstation, such as Claude Code or OpenCode, work on HPC
clusters through FirecREST: browse and transfer files, and submit and monitor Slurm
jobs. The agent runs locally and reaches the cluster only through this server's tools.
A config file limits what the tools can do (see [Config file](#config-file)).
[Restrictions](docs/restrictions.md) lists the ways the server limits the agent and what
it doesn't restrict.

The server is built for CSC's LUMI and Roihu, which get cluster-specific instructions
for the agent. Other clusters with a FirecREST v2 API should work without them, and can
be given their own (see [Other clusters](#other-clusters)).

## Installation

Install the server as a [uv](https://docs.astral.sh/uv/) tool:

```bash
git clone <repo-url>
cd firecrest-mcp
uv tool install .
```

Add the server to your agent's global MCP configuration once for each cluster you want
to use. This makes it available wherever you start the agent.
`examples/claude-code/mcp.json` and `examples/opencode/opencode.json` have entries for
LUMI and Roihu that you can add to your Claude Code or OpenCode configuration. They
start the server with `uvx firecrest-mcp`, which runs the version installed with
`uv tool install .`.

To update the server, pull the latest changes in the repo and run
`uv tool install --reinstall .` there.

## Usage

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

To keep the token somewhere else, set the `FIRECREST_TOKEN_PATH` environment variable in
each server's entry in your MCP configuration. In Claude Code:

```json
"env": {
  "FIRECREST_URL": "https://api.lumi.csc.fi/v1",
  "FIRECREST_TOKEN_PATH": "~/secrets/firecrest-token"
}
```

OpenCode calls the same setting `environment`.

Each local project you use with FirecREST gets its own config file,
`.firecrest-mcp.toml`, which limits what the agent working in that project can do on the
clusters. Copy the example config into the project directory:

```bash
cp path/to/firecrest-mcp/examples/firecrest-mcp.toml .firecrest-mcp.toml
```

Then edit it (see [Config file](#config-file)). The server reads it on every call, so
changes take effect without restarting the agent. The server looks for the config in the
directory the agent starts in, so start the agent from the project directory.

## Config file

Tools only accept what the project's `.firecrest-mcp.toml` allows. A missing file
or key allows none of the operations it controls, and unknown keys are errors. Each
cluster has a table named after its `FIRECREST_URL` host (`api.roihu.csc.fi` is
`[roihu]`), and the table covers all of the cluster's FirecREST systems (`cpu` and `gpu`
on Roihu, `lumi` on LUMI). See `examples/firecrest-mcp.toml` for every key.

Status tools, and job tools other than the `submit` tool, work without a config, since
they only read the cluster's status or act on your own jobs, with no paths or accounts
to check.

The file tools for copying, moving, deleting, compressing, extracting, uploading and
downloading need an account, because they may run a transfer job, a Slurm job that
FirecREST starts for large or slow file operations. The account is required even if no
transfer job runs. The agent can name the account when it calls the tool, or you can set
`default_account` in the config so that it doesn't have to.

The `groups` key lists the groups that the `chgrp` tool may set on a file. This lets the
agent share a file you moved into a project directory with the project's members.

### Paths

Paths on the cluster must lie in or below an entry of `remote_paths`. Wildcards such as
`*` don't work in the entries. Remote paths must be absolute and must not contain `..`,
single quotes or control characters. Symlinks on the cluster aren't resolved, so a link
inside an allowed directory can lead outside it. On LUMI, `/project` and `/projappl` are
the same directory, so the server allows both names when the config lists either.

The upload, download and submit tools use paths on your workstation, which must lie in
or below an entry of `local_paths`. Wildcards don't work here either. Local paths may be
relative to the project directory, and they're resolved before they're checked, so a
symlink can't lead outside `local_paths`. The config file, `.mcp.json`, `.claude/`,
`.git/` and the token file are always denied. **Nothing else is protected, so don't list
your home directory or other places with credentials, such as `~/.ssh`, in
`local_paths`.**

### Jobs

The `submit` tool checks the account, partition and reservation in its arguments, which
must be listed in the config, and the working directory, which must be under
`remote_paths`. It always passes an account and partition, using `default_account` and
`default_partition` when the agent gives none. These override the job script's `#SBATCH`
lines, as command-line options do with `sbatch`. For example, a job submitted with
`account="project_1"` and `#SBATCH -A project_2` is billed to `project_1`.

**The tool doesn't check the job script.** The script can set an unlisted reservation if
the agent doesn't pass one, and its commands run with all of your permissions, also
outside `remote_paths`.

**Transfer jobs run in the partition that FirecREST is set up to use for them
(`interactive` on LUMI and Roihu), even if `partitions` in the config doesn't list it.**

Job tools only show your own jobs, and refuse another user's job ID.

## Other clusters

The server should work with any cluster that has a FirecREST v2 API, though it has only
been used on LUMI and Roihu. The `FIRECREST_URL` environment variable, set in the
server's entry in your MCP configuration, points the server at a cluster's API, and the
server won't start without it. To adapt the server to another cluster:

- Add a server entry for the cluster to your MCP configuration, with its
  `FIRECREST_URL`. The server names the cluster after the first part of the API's host
  name other than `api`, and uses that name for the cluster's table in the config file.
  For example, `https://api.hpc.example.org/v1` is the cluster `hpc`, with the table
  `[hpc]`.
- Optionally, add `src/firecrest_mcp/context/<cluster name>.md` (e.g. `hpc.md`) with
  instructions for the agent, such as its partitions and file systems (see `lumi.md`),
  and reinstall. A file with any other name is ignored without a warning.
- If a directory has two names, as `/project` and `/projappl` do on LUMI, add it to
  `PATH_ALIASES` in `src/firecrest_mcp/policy.py`.

## Development

The repo is set up as a project of its own, with a `.firecrest-mcp.toml` in the repo
root that git ignores. Its `.mcp.json` starts the server with `uv run`, which takes
precedence over your global servers of the same name, so the server uses the checked-out
code. Restart Claude Code after switching branches or editing the code.

Install the pre-commit hooks, which run `ruff check`, `ruff format --check` and
`ty check` before each commit:

```bash
uv run pre-commit install
```
