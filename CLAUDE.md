# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in
this repository.

## Commands

Python ≥3.13, managed with `uv`.

```bash
uv run pytest                                  # all tests
uv run pytest tests/config/test_tools.py       # one file
uv run pytest -k "symlink"                     # tests matching a name
uv run ruff check                              # lint
uv run ty check                                # type check
uv run ruff format                             # format
uv run pre-commit run --all-files              # all pre-commit hooks
```

The pre-commit hooks (`.pre-commit-config.yaml`) are local hooks that call `uv run`, so
ruff, ty and pytest versions come from `uv.lock`. They run ruff, ty and the whole test
suite. They only check, so `ruff format` must be run by hand when the format hook
fails.

Running the server needs `FIRECREST_URL` (e.g. `https://api.lumi.csc.fi/v1`) and a
token file at `~/.firecrest-token` (or `FIRECREST_TOKEN_PATH`) with mode 600.
`examples/claude-code/` holds Claude Code configs with entries for LUMI and Roihu.
`mcp-stdio.json` runs the `uv tool install .` copy as `firecrest-mcp`, and
`mcp-http.json` connects to servers on ports 8000 and 8001. The top-level `dev/` holds
the same two for development, with servers named `firecrest-lumi-dev` and `firecrest-roihu-dev` so
they don't clash with installed ones. `dev/mcp-stdio.json` runs the checked-out code
with `uv run firecrest-mcp`, and Claude Code must be restarted to pick up code changes.
Servers behind `dev/mcp-http.json` must be restarted instead. A developer copies one of
them to `.mcp.json` in the repo root, which git ignores. `examples/` also holds a
sample `firecrest-mcp.toml` that a test loads.

`main()` in `src/firecrest_mcp/__init__.py` runs the server over stdio by default.
`--transport http` with `--host`, `--port` and `--allowed-host` serves an agent in a
container on the same workstation. Over HTTP the server always checks the `Host`
header, and `--allowed-host` adds names to `127.0.0.1`, `localhost`, `::1` and the
`--host` address, which FastMCP allows by itself.

## Architecture

An MCP server (FastMCP) that wraps the `pyfirecrest` v2 client
(`firecrest.v2.Firecrest`) to expose HPC file and Slurm operations on CSC systems.

- **Tool registration** (`src/firecrest_mcp/server.py`): tools live as
  `@tool()`-decorated methods on three mixins in `tools/` (`compute`, `filesystem`,
  `status`), combined into `FirecrestClientWrapper`, which holds `self.client`. The
  server then registers every public method of the wrapper that has `@tool()`, as
  FastMCP's own discovery of tools in a module does. A helper method without
  `@tool()` is not a tool.
  The `config` tool doesn't call FirecREST, so it isn't on a mixin. `server.py`
  registers `active_config()` from `config.py` under that name.
  `tests/test_server.py` checks that the server registers exactly the mixins' tools
  and `config`. The only list of the mixins' tool names is `TOOLS_RESTRICTED` and
  `TOOLS_NOT_RESTRICTED` in `tests/config/test_tools.py`.
- **Tests through FastMCP**: most tool tests call the mixin methods directly, which
  skips FastMCP's validation of the arguments and its conversion of the result.
  `test_tool_works_through_fastmcp` in `tests/config/test_tools.py` calls every tool
  once with `call_through_mcp`. `MOCK_CLIENT_RESULTS` there holds what the mock
  client returns for a tool. A tool that isn't listed returns an empty dict. The
  patterns on `SystemName` and `JobId` in `tools/params.py` are checked only by
  FastMCP, so their tests use `call_through_mcp`.
- **Client calls**: pass everything after `system_name` to `self.client` methods by
  keyword. pyfirecrest's untyped `_with_correlation_id` decorator hides their
  signatures from ty, so only the names catch a wrong argument. The tests' mock
  client is a `create_autospec(Firecrest)`, which rejects unknown names.
- **Import-time side effects**: `server.py` reads `FIRECREST_URL` and raises if it's
  missing, so tests import the mixins (or `auth`) directly with a mock `client` rather
  than importing `server`. Only `tests/test_server.py` imports it, after setting
  `FIRECREST_URL`.
- **Instructions**: the FastMCP `instructions` are `ground_rules.md`, sent by every
  server, followed by `context/<cluster>.md` if it exists, where `<cluster>` is
  `cluster_name()` (see below). Each file starts with a `###` header, because Claude
  Code puts each server's instructions under a `##` header. One server process serves
  one system, so each config has two entries.
- **Auth** (`auth.py`, tested in `tests/test_auth.py`): `TokenAuth.get_access_token`
  re-reads the token file on every request (so users can refresh it in place), refuses
  it if group/other permission bits are set, and checks the JWT `exp` without
  verifying the signature.
- **Caching**: read-only status/job-query tools are wrapped in
  `cachetools.func.ttl_cache` (stacked under `@tool()`).

### Config file

`config.py` enforces `.firecrest-mcp.toml` (see README), read on every call and
failing closed. `cluster_name()` picks the `[<cluster>]` table from the `FIRECREST_URL`
host; it applies to every `system_name`. Tools check all of their checked arguments
before calling the client:

- `load_cluster_config().check_remote_paths(*paths)` for remote paths, skipping
  `None`. `PATH_ALIASES` lists directories a cluster reaches under two names (LUMI's
  `/project` and `/projappl`).
- `check_local_paths(*paths)` for local paths, skipping `None`.
- `ClusterConfig.checked_account(account)` for accounts. It returns
  `default_account` for `None`. Pass the result on to the client. Tools that may run
  a transfer job call `checked_transfer(account, *paths)`, which checks both.
- `ClusterConfig.check_group(group)` for `chgrp`.
- `own_jobs(client, system_name, jobs, jobid)` in `tools/compute.py` for job
  queries, and `check_own_job(client, system_name, jobid)` there for tools that act on
  a job by ID, since FirecREST returns any user's job by ID. They don't depend on the
  config.
- `ClusterConfig.checked_job_options` for `submit`. It checks the arguments, not the
  script, and returns an account and partition that always override the script's
  `#SBATCH` lines.

When changing a tool's checked parameters, update `TOOLS_RESTRICTED` (and
`TOOLS_WITH_ACCOUNT`) in `tests/config/test_tools.py`. A new tool goes into
`TOOLS_RESTRICTED`, or into `TOOLS_NOT_RESTRICTED` if the config controls none of its
arguments, and into `MOCK_CLIENT_RESULTS` if the client returns something other than
a dict for it. The `config` fixture in `tests/config/conftest.py` chdirs into a temp dir
and returns a function that writes the config there.

`pytest` runs with `--import-mode=importlib` (set in `pyproject.toml`).
