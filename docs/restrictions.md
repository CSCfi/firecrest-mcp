# Restrictions

The agent reaches the cluster only through the server's tools, and each tool checks its
arguments before it calls FirecREST. This page lists the ways the server limits the
agent, and ends with what it doesn't restrict. The
[README](../README.md#config-file) explains how to write the config file that most of
them read.

## Checking the token

The server reads the token from `~/.firecrest-token`, or from `FIRECREST_TOKEN_PATH`, on
every request. Like ssh with a private key, it refuses the file if anyone but the user
can access it. It also refuses an empty or expired token. It checks only the token's
`exp` claim, not its signature. FirecREST checks the token itself.

## Leaving operations and arguments out

The server offers only a subset of the pyfirecrest v2 client as tools:

| Group | Tools |
|---|---|
| Status | `systems`, `partitions`, `reservations`, `userinfo` |
| Files | `list_files`, `read_file`, `checksum`, `stat`, `chmod`, `chgrp`, `symlink`, `mkdir`, `mv`, `cp`, `rm`, `compress`, `extract` |
| Transfer | `upload`, `download` |
| Jobs | `submit`, `job_info`, `job_metadata`, `cancel_job`, `attach_to_job` |

The tools leave out these parts of the client:

- `nodes`, `file_type` and `wait_for_job` are left out. `partitions`, `read_file` and
  `job_info` cover most of what they are used for.
- `chown` is offered only as `chgrp`, which changes a file's group, because only root
  can change a file's owner.
- `compress` has no `match_pattern` argument. FirecREST puts the pattern into a shell
  command without escaping it, so a pattern could run any command on the cluster.

## Refusing unsafe formats

FirecREST puts some arguments into shell commands without escaping them, so the server
refuses values that could change those commands or the path they name:

- A path on the cluster is refused if it is not absolute, contains a `..` component, or
  contains a single quote or a control character. FirecREST puts paths in single
  quotes, so a quote would end the path.
- `chmod` takes only a numeric mode of three or four octal digits, such as `750`.

## Always refusing certain values

Some files on the workstation configure the server and the agent, or hold the token.
Overwriting them with `download` could widen what the agent may do or make it run
commands, and `upload` could send the token to the cluster. So the server refuses
these paths even if `local_paths` allows them:

- the config file `.firecrest-mcp.toml`,
- `.mcp.json`, `.claude/` and `.git/` in the project directory,
- the token file.

## Allowing only listed values

`.firecrest-mcp.toml` lists the paths, accounts, partitions, reservations and groups
that the agent may use. For these arguments, anything the file doesn't explicitly
allow is denied. The server for a cluster reads only that cluster's table, so it never
applies another cluster's lists, and a mistake in another table doesn't affect it.
`local_paths` is a top-level list that applies to all clusters.

| Argument | Tools | List |
|---|---|---|
| A path on the cluster | All file, transfer and job tools that take one | `remote_paths`, the entry itself or below it |
| A path on the workstation | `upload`, `download`, and `submit` with `script_local_path` | `local_paths`, the entry itself or below it |
| Account | `mv`, `cp`, `rm`, `compress`, `extract`, `upload`, `download`, `submit` | `accounts` |
| Partition, reservation | `submit` | `partitions`, `reservations` |
| Group | `chgrp` | `groups` |

Slurm accepts several partitions or reservations separated by commas, and the server
allows such a value if every item in it is listed. An account or partition the agent
leaves out is replaced with `default_account` or `default_partition`. If
`default_account` isn't in `accounts` or `default_partition` isn't in `partitions`, the
config is invalid and every tool that reads it fails.

A path, on the cluster or on the workstation, is allowed if it is an entry or lies
below one:

- Paths are compared by whole components, so `/scratch/project_10` is not under
  `/scratch/project_1`. Wildcards in the entries are not expanded.
- On the cluster, LUMI's `/project` and `/projappl` count as the same directory, so
  either name in the file allows both. `symlink` checks both the path of the new link
  and the path it points to, and `upload` checks the target directory joined with the
  file name.
- On the workstation, the server checks where a path really leads, so a symlink or
  `..` can't reach outside `local_paths`. Relative paths start from the project
  directory.

## Setting values instead of the agent

The server fills in or replaces some values, so that FirecREST and Slurm don't choose
them:

- `mv`, `cp`, `rm`, `compress`, `extract`, `upload` and `download` may start a transfer
  job, so they always pass an account, even when no job runs. If the agent gives none,
  they use `default_account`, and fail if that is not set.
- `submit` always passes an account and a partition, using `default_account` and
  `default_partition` when none is given, and fails if a default is not set. These
  override the job script's `#SBATCH` lines. The script can still set an unlisted
  reservation if the agent doesn't pass one. Environment variables given to `submit`
  reach only the running job, not Slurm.
- `job_info` always asks for the user's own jobs only (`allusers=False`).

## Filtering results by owner

FirecREST returns any user's job when asked for it by ID. `job_info` drops jobs that
don't belong to the user, and `job_metadata`, `cancel_job` and `attach_to_job` refuse a
job ID that belongs to someone else. The user's name comes from `userinfo` and is cached
for three minutes.

## What the server doesn't restrict

The restrictions above don't stop the agent from doing the following, so take them into
account before giving it a token:

- **Running any command with all of the user's permissions**, in a submitted job or
  with `attach_to_job`. `submit` doesn't read the job script, so the script can read
  and write files outside `remote_paths`.
- **Editing `.firecrest-mcp.toml` with its own file tools**, which would undo every
  restriction above. Only the agent's own permission settings can prevent this.
- Sending any file in `local_paths` to the cluster. Only `.firecrest-mcp.toml`,
  `.mcp.json`, `.claude/`, `.git/` and the token file are protected.
- Following a symlink on the cluster from inside `remote_paths` to outside it.
- Reading anything a job writes to an allowed directory.
- Starting transfer jobs in FirecREST's transfer partition (`interactive` on LUMI and
  Roihu), even if `partitions` doesn't list it.
- Using the status tools and the job query tools on any system the token reaches.
