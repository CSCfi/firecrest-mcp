# CLAUDE.md

## Commands

```bash
uv run pytest                                  # all tests
uv run pytest tests/config/test_tools.py       # one file
uv run pytest -k "symlink"                     # tests matching a name
uv run ruff check                              # lint
uv run ty check                                # type check
uv run ruff format                             # format
uv run pre-commit run --all-files              # all pre-commit hooks
```

The pre-commit hooks only check, so run `uv run ruff format` by hand when the format
hook fails.

Running the server needs `FIRECREST_URL` and a token file, as the README's Setup
section says. `dev/mcp-stdio.json` and `dev/mcp-http.json` run the checked-out code.
They pick up code changes only after a restart of Claude Code or of the HTTP servers.

## Architecture

An MCP server (FastMCP) that wraps the `pyfirecrest` v2 client
(`firecrest.v2.Firecrest`) to expose HPC file and Slurm operations on CSC systems.
One server process serves one cluster, chosen by `FIRECREST_URL`.

- **Tool registration** (`server.py`): tools that call FirecREST are `@tool()` methods
  on the mixins in `tools/`, which `FirecrestClientWrapper` combines. Tools that don't,
  such as `show_config`, are `@tool()` functions in `tools/clientless.py`. `server.py`
  registers every public `@tool()` method of the wrapper, and each of those functions
  by name.
- **Tests through FastMCP**: most tool tests call the mixin methods directly, which
  skips FastMCP's checks of the arguments, such as the patterns in `tools/params.py`,
  and its conversion of the result. Use `call_through_mcp` in
  `tests/config/test_tools.py` to test those.
- **Client calls**: pass everything after `system_name` to `self.client` methods by
  keyword. pyfirecrest's untyped `_with_correlation_id` decorator hides their
  signatures from ty, so only the names catch a wrong argument. The tests' mock
  client is a `create_autospec(Firecrest)`, which rejects unknown names.
- **Import-time side effects**: `server.py` reads `FIRECREST_URL` and raises if it's
  missing, so tests import the mixins (or `auth`) directly with a mock `client` rather
  than importing `server`. Only `tests/test_server.py` imports it, after setting
  `FIRECREST_URL`.
- **Instructions**: the FastMCP `instructions` are `context/shared.md`, sent by every
  server, followed by `context/clusters/<cluster>.md` if it exists, where `<cluster>` is
  `cluster_name()`. Each file starts with a `###` header, because Claude Code puts each
  server's instructions under a `##` header. A cluster's context file holds only what
  the instructions must say: the pointer to the cluster's documentation MCP server,
  facts that this server's tools or config depend on, and facts that agents get
  confidently wrong. Anything the documentation server covers, or that only describes
  the platform, stays out.
- **Auth** (`auth.py`, tested in `tests/test_auth.py`): `TokenAuth.get_access_token`
  re-reads the token file on every request (so users can refresh it in place), refuses
  it if group/other permission bits are set, and checks the JWT `exp` without
  verifying the signature.
- **Caching**: read-only status and job-query tools are wrapped in `ttl_cache` under
  `@tool()`. A tool that changes jobs calls `job_info.cache_clear()`, as `submit` and
  `cancel_job` do.

### Config file

`config.py` reads `.firecrest-mcp.toml` on every call and fails closed. Tools check all
of their checked arguments before calling the client:

- `load_cluster_config().check_remote_paths(*paths)` for remote paths.
- `check_local_paths(*paths)` for local paths.
- `ClusterConfig.checked_account(account)` for accounts. It returns
  `default_account` for `None`. Pass the result on to the client. Tools that may run
  a transfer job call `checked_transfer(account, *paths)`, which checks both.
- `ClusterConfig.check_group(group)` for `chgrp`.
- `own_jobs(client, system_name, jobs, jobid)` in `tools/compute.py` for job queries,
  and `check_own_job(client, system_name, jobid)` for tools that act on a job by ID,
  because FirecREST returns any user's job by ID.
- `ClusterConfig.checked_job_options` for `submit`. Pass the account and partition it
  returns to the client, because they override the script's `#SBATCH` lines.

When changing a tool's checked parameters, update `TOOLS_RESTRICTED` and
`TOOLS_WITH_ACCOUNT` in `tests/config/test_tools.py`. A new tool goes into
`TOOLS_RESTRICTED`, or into `TOOLS_NOT_RESTRICTED` if the config controls none of its
arguments, and into `MOCK_CLIENT_RESULTS` if the client returns something other than
a dict for it.
