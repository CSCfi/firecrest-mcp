"""Parameter types that several tools share."""

from typing import Annotated, Literal

from pydantic import Field

# FastMCP shows a string in Annotated to the agent as the parameter's description.
# Field(description=...) does the same where a pattern is needed too.

# pyfirecrest puts the system name into the request URL unchanged, so "/", "?" or
# ".." in it change which URL is requested. FastMCP checks the pattern before the
# tool runs.
SystemName = Annotated[
    str,
    Field(
        description="the system name, as listed by the systems tool",
        pattern="^[A-Za-z0-9_-]+$",
    ),
]
# pyfirecrest also puts the job ID into the request URL unchanged. The pattern is the
# one FirecREST's job endpoints check.
JobId = Annotated[
    str,
    Field(description="the ID of the job", pattern="^[a-zA-Z0-9]+$"),
]
RemotePath = Annotated[str, "an absolute path on the system"]
TransferAccount = Annotated[
    str | None,
    "the account for the transfer job, if one is needed; defaults to the"
    " default_account in the config",
]
Blocking = Annotated[bool, "wait for the transfer job, if one is needed, to finish"]
Timeout = Annotated[float | None, "the maximum time in seconds to wait for the job"]
Compression = Annotated[
    Literal["none", "gzip", "bzip2", "xz"], "the compression algorithm"
]
