# Safeguards

The agent reaches the cluster only through the server's tools, and each tool checks its
arguments before it calls FirecREST. This page lists the server's safeguards, grouped
by what they apply to, and ends with their limitations. The
[README](../README.md#config-file) explains how to write the config file that most of
them read.

## Token

The server reads the token from `~/.firecrest-token`, or from the file that
`--token-file` names, on every request. Like ssh with a private key, it refuses the
file if anyone but the user can access it. It also refuses an empty or expired token.
It checks only the token's `exp` claim, not its signature. FirecREST checks the token
itself.

## Tools

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

`chmod` takes only a numeric mode of three or four octal digits, such as `750`, because
FirecREST puts the mode into a shell command without escaping it.

## Config file

`.firecrest-mcp.toml` lists the paths, accounts, partitions, reservations and groups
that the agent may use. For these arguments, anything the file doesn't explicitly
allow is denied. The server for a cluster reads only that cluster's table, so it never
applies another cluster's lists, and a mistake in another table doesn't affect it.
`local_paths` is a top-level list that applies to all clusters.

The `show_config` tool returns the parts of the file that its server applies,
`local_paths` and the cluster's table, with every key and an empty list or null for a
missing one. It fails with the same error as the other tools when the file is missing
or invalid.

## Local paths

`upload`, `download`, and `submit` with `script_local_path` take a path on the
workstation. It must be an entry of `local_paths` or lie below one. Paths are compared
by whole components, so `data_old` is not under `data`. Wildcards in the entries are
not expanded. The server checks where the path really leads, so a symlink or `..` can't
reach outside `local_paths`. The check holds when the tool is called. A link that
replaces a directory in the path afterwards, while a transfer runs, is followed.
Relative paths start from the project directory. An empty entry is a config error, so
the whole project directory must be written as `.`.

An entry must not contain a symlink, because changing the link would change which
directory `local_paths` allows. The error names the entry's real path, which can be
listed instead. Paths below it can still be given through the link.

Overwriting the config file with `download` would widen what the tools may do, and
`upload` could send the token to the cluster. Writing into `.git/` could replace your
repository or add a hook that git runs. The server refuses these paths even if
`local_paths` allows them:

- the config file `.firecrest-mcp.toml`, and the file that `--config` names if it is
  given,
- the token file,
- `.git/` in the project directory.

It also refuses a hard link to one of them and, on a file system that ignores case,
another spelling of one that exists.

## System names and job IDs

Every tool except `systems` takes a system name, which pyfirecrest puts into the request
URL unchanged. The server accepts only letters, digits, `_` and `-` in it, so a system
name can't change which URL a tool requests. Job IDs go into the URL the same way, and
the server accepts only letters and digits in them, as FirecREST's job endpoints do.

## Remote paths

All file, transfer and job tools that take a path on the cluster check it:

- The path must be absolute and must not contain a `..` component, a single quote or a
  control character. FirecREST puts paths into shell commands in single quotes, so a
  quote would end the path.
- The path must not contain a space or any of `"\;&|<>()$` and the backtick. FirecREST
  releases up to 2.6.2 put the path of a large download into a transfer job script
  without quotes, and that of a large upload in double quotes, where these characters
  could run commands.
- The path must be an entry of `remote_paths` or lie below one, compared by whole
  components and without wildcards, as local paths are.
- LUMI's `/project` and `/projappl` count as the same directory, so either name in the
  file allows both.
- `symlink` checks both the path of the new link and the path it points to. `upload`
  checks the target directory joined with the file name, and refuses a file name that
  is empty or contains `/`.

The server doesn't resolve symlinks on the cluster, so a link inside `remote_paths` can
lead outside it.

## Accounts, partitions, reservations and groups

| Argument | Tools | List |
|---|---|---|
| Account | `mv`, `cp`, `rm`, `compress`, `extract`, `upload`, `download`, `submit` | `accounts` |
| Partition, reservation | `submit` | `partitions`, `reservations` |
| Group | `chgrp` | `groups` |

Slurm accepts several partitions or reservations separated by commas, and the server
allows such a value if every item in it is listed. If `default_account` isn't in
`accounts` or `default_partition` isn't in `partitions`, the config is invalid and every
tool that reads it fails.

`mv`, `cp`, `rm`, `compress`, `extract`, `upload` and `download` may start a transfer
job, so they always pass an account, even when no job runs. If the agent gives none,
they use `default_account`, and fail if that is not set.

## Jobs

`submit` always passes an account and a partition, using `default_account` and
`default_partition` when none is given, and fails if a default is not set. These
override the job script's `#SBATCH` lines. The script can still set an unlisted
reservation if the agent doesn't pass one. Environment variables given to `submit`
reach only the running job, not Slurm.

FirecREST returns any user's job when asked for it by ID. `job_info` always asks for the
user's own jobs only (`allusers=False`) and drops jobs that don't belong to the user.
`job_metadata`, `cancel_job` and `attach_to_job` refuse a job ID that belongs to someone
else. The user's name comes from `userinfo` and is cached for three minutes.

## Limitations

The safeguards above don't stop the agent from doing the following, so take them into
account before giving it a token:

- **Running any command with all of the user's permissions**, in a submitted job or
  with `attach_to_job`. `submit` doesn't read the job script, so the script can read
  and write files outside `remote_paths`.
- **Editing `.firecrest-mcp.toml` with its own file tools**, which would undo every
  safeguard above. The server's instructions tell the agent not to, but only the
  agent's own permission settings can stop it. The
  [README](../README.md#agent-permissions) has an example for Claude Code. An agent in
  a container can't reach a config outside the project that the server reads with
  `--config`, as [Connecting over HTTP](http.md) describes.
- Sending any file in `local_paths` to the cluster, or overwriting one with
  `download`. Only the config files, the token file and `.git/` are protected.
- Following a symlink on the cluster from inside `remote_paths` to outside it.
- Reading anything a job writes to an allowed directory.
- Starting transfer jobs in FirecREST's transfer partition (`interactive` on LUMI and
  Roihu), even if `partitions` doesn't list it.
- Using the status tools and the job query tools on any system the token reaches.
