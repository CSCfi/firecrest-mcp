"""Parameter types that several tools share."""

from typing import Annotated, Literal

SystemName = Annotated[str, "the system name, as listed by the systems tool"]
RemotePath = Annotated[str, "an absolute path on the system"]
Account = Annotated[
    str | None,
    "the account for the transfer job, if one is needed; defaults to the"
    " default_account in the config",
]
Blocking = Annotated[bool, "wait for the transfer job, if one is needed, to finish"]
Timeout = Annotated[float | None, "the maximum time in seconds to wait for the job"]
Compression = Annotated[
    Literal["none", "gzip", "bzip2", "xz"], "the compression algorithm"
]
