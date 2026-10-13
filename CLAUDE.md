# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in
this repository.

## Commands

Python ≥3.13, managed with `uv`.

```bash
uv run pytest                                  # all tests
uv run pytest tests/policy/test_tools.py       # one file
uv run pytest -k "symlink"                     # tests matching a name
uv run ruff check                              # lint
uv run ty check                                # type check
uv run ruff format                             # format
uv run pre-commit run --all-files              # all pre-commit hooks
```

The pre-commit hooks (`.pre-commit-config.yaml`) are local hooks that call `uv run`, so
ruff and ty versions come from `uv.lock`. They check only; `ruff format` must be run
by hand when the format hook fails.

Running the server needs `FIRECREST_URL` (e.g. `https://api.lumi.csc.fi/v1`) and a
token file at `~/.firecrest-token` (or `FIRECREST_TOKEN_PATH`) with mode 600.
`.mcp.json` starts the checked-out code via `uv run firecrest-mcp` for LUMI and Roihu;
Claude Code must be restarted to pick up code changes. `examples/` holds end-user
client configs that use `uvx` against the `uv tool install .` copy, and a sample
`firecrest-mcp.toml` that a test loads.

## Architecture

An MCP server (FastMCP) that wraps the `pyfirecrest` v2 client
(`firecrest.v2.Firecrest`) to expose HPC file and Slurm operations on CSC systems.

- **Tool registration** (`src/firecrest_mcp/server.py`): tools live as
  `@tool()`-decorated methods on three mixins in `tools/` (`compute`, `filesystem`,
  `status`), combined into `FirecrestClientWrapper`, which holds `self.client`. The
  server then registers **every callable non-dunder attribute** of the wrapper as an
  MCP tool, so any helper method added to a mixin becomes a tool too — keep helpers
  out of the mixins (or make them module-level functions).
- **Client calls**: pass everything after `system_name` to `self.client` methods by
  keyword. pyfirecrest's untyped `_with_correlation_id` decorator hides their
  signatures from ty, so only the names catch a wrong argument. The tests' mock
  client is a `create_autospec(Firecrest)`, which rejects unknown names.
- **Import-time side effects**: `server.py` reads `FIRECREST_URL` and raises if it's
  missing, so tests import the mixins (or `auth`) directly with a mock `client` rather
  than importing `server`.
- **Per-system instructions**: `context/<cluster>.md`, if it exists, is passed as the
  FastMCP `instructions`, where `<cluster>` is `cluster_name()` (see below). One server
  process serves one system; `.mcp.json` runs two instances.
- **Auth** (`auth.py`, tested in `tests/test_auth.py`): `TokenAuth.get_access_token`
  re-reads the token file on every request (so users can refresh it in place), refuses
  it if group/other permission bits are set, and checks the JWT `exp` without
  verifying the signature.
- **Caching**: read-only status/job-query tools are wrapped in
  `cachetools.func.ttl_cache` (stacked under `@tool()`).

### Config file

`policy.py` enforces `.firecrest-mcp.toml` (see README), read on every call and
failing closed. `cluster_name()` picks the `[<cluster>]` table from the `FIRECREST_URL`
host; it applies to every `system_name`. Tools check all of their checked arguments
before calling the client:

- `load_cluster().check_remote_paths(*paths)` for remote paths, skipping `None`.
  `PATH_ALIASES` lists directories a cluster reaches under two names (LUMI's
  `/project` and `/projappl`).
- `check_local_paths(*paths)` for local paths, skipping `None`.
- `ClusterPolicy.account(account)` for accounts. It returns `default_account` for
  `None`; pass the result on to the client. Tools that may run a transfer job call
  `check_transfer(account, *paths)`, which checks both.
- `ClusterPolicy.check_group(group)` for `chgrp`.
- `own_jobs(client, system_name, jobs, jobid)` for job queries and for tools that act
  on a job by ID, since FirecREST returns any user's job by ID.
- `submit` reads the script itself, checks it with `ClusterPolicy.job_options`
  (`#SBATCH` parsing is in `sbatch.py`) and submits it as `script_str`.

When changing a tool's checked parameters, update `TOOL_CALLS` (and `ACCOUNT_TOOLS`)
in `tests/policy/test_tools.py`. The `config` fixture in `tests/policy/conftest.py`
chdirs into a temp dir and returns a function that writes the config there.

`pytest` runs with `--import-mode=importlib` (set in `pyproject.toml`).
