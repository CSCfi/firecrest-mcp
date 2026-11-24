"""Tools for files on the system, and for uploading and downloading them."""

import posixpath
import re
from stat import S_ISDIR
from typing import Annotated

from fastmcp.exceptions import ToolError
from fastmcp.tools import tool
from firecrest.v2 import Firecrest

from firecrest_mcp.config import load_config
from firecrest_mcp.tools.params import (
    Blocking,
    Compression,
    RemotePath,
    SystemName,
    Timeout,
    TransferAccount,
)


class FirecrestFilesystemToolsMixin:
    client: Firecrest

    def _use_direct_transfer_limit(self, system_name: str) -> None:
        """Set the size under which pyfirecrest uploads or downloads a file in one
        request to the system's limit for that.

        pyfirecrest's own limit is 1 MiB, while a system's FirecREST may allow more.
        The limit stays unchanged if the system isn't in the list of systems.
        """
        for system in self.client.systems():
            if system["name"] == system_name:
                limit = system["dataOperation"]["max_ops_file_size"]
                self.client.MAX_DIRECT_UPLOAD_SIZE = limit
                return

    @tool()
    def list_files(
        self,
        system_name: SystemName,
        path: RemotePath,
        show_hidden: Annotated[bool, "show hidden files"] = False,
        recursive: Annotated[bool, "list subdirectories recursively"] = False,
        dereference: Annotated[
            bool, "show the files that symbolic links point to, not the links"
        ] = False,
    ) -> list[dict]:
        """Returns a list of files in a directory."""
        load_config().check_remote_paths(path)
        return self.client.list_files(
            system_name,
            path=path,
            show_hidden=show_hidden,
            recursive=recursive,
            dereference=dereference,
        )

    @tool()
    def read_file(
        self,
        system_name: SystemName,
        path: RemotePath,
        first_lines: Annotated[int | None, "return only the first N lines"] = None,
        last_lines: Annotated[int | None, "return only the last N lines"] = None,
    ) -> str:
        """Read a text file: the whole file (up to 5 MB), or only its first or last
        lines.
        """
        load_config().check_remote_paths(path)
        if first_lines is not None and last_lines is not None:
            raise ToolError("Give at most one of first_lines and last_lines.")
        if first_lines is not None:
            output = self.client.head(system_name, path=path, num_lines=first_lines)
        elif last_lines is not None:
            output = self.client.tail(system_name, path=path, num_lines=last_lines)
        else:
            return self.client.view(system_name, path=path)
        # head and tail also report positions, but only the text is of use here.
        # FirecREST's schema allows a null output.
        return output["content"] if output else ""

    @tool()
    def checksum(self, system_name: SystemName, path: RemotePath) -> dict:
        """Calculate the SHA256 (256-bit) checksum of a specified file."""
        load_config().check_remote_paths(path)
        return self.client.checksum(system_name, path=path)

    @tool()
    def chmod(
        self,
        system_name: SystemName,
        path: RemotePath,
        mode: Annotated[str, "a numeric mode, as for chmod, e.g. 750"],
    ) -> dict:
        """Changes the file mod bits of a given file according to the specified mode."""
        load_config().check_remote_paths(path)
        # FirecREST puts the mode into a shell command without escaping it, so only
        # an octal number is passed on.
        if not re.fullmatch("[0-7]{3,4}", mode):
            raise ToolError(f"Mode {mode!r} is not a numeric mode such as 750.")
        return self.client.chmod(system_name, path=path, mode=mode)

    @tool()
    def chgrp(
        self,
        system_name: SystemName,
        path: RemotePath,
        group: Annotated[str, "the new group, e.g. a project group"],
    ) -> dict:
        """Change the group of a file, e.g. to share it with a project. Its owner is
        not changed.
        """
        config = load_config()
        config.check_remote_paths(path)
        config.check_group(group)
        # An empty owner leaves the owner as it is.
        return self.client.chown(system_name, path=path, owner="", group=group)

    @tool()
    def stat(
        self,
        system_name: SystemName,
        path: RemotePath,
        dereference: Annotated[bool, "follow symbolic links"] = False,
    ) -> dict:
        """Uses the stat linux application to determine the status of a file on the
        system's filesystem. The result follows:
        https://docs.python.org/3/library/os.html#os.stat_result.
        """
        load_config().check_remote_paths(path)
        return self.client.stat(system_name, path=path, dereference=dereference)

    @tool()
    def symlink(
        self,
        system_name: SystemName,
        source_path: Annotated[str, "the absolute path that the link points to"],
        link_path: Annotated[str, "the absolute path of the new link"],
    ) -> dict:
        """Create a symbolic link."""
        load_config().check_remote_paths(source_path, link_path)
        return self.client.symlink(
            system_name, source_path=source_path, link_path=link_path
        )

    @tool()
    def mkdir(
        self,
        system_name: SystemName,
        path: RemotePath,
        create_parents: Annotated[bool, "create missing parent directories"] = False,
    ) -> dict:
        """Create a directory."""
        load_config().check_remote_paths(path)
        return self.client.mkdir(system_name, path=path, create_parents=create_parents)

    @tool()
    def mv(
        self,
        system_name: SystemName,
        source_path: RemotePath,
        target_path: RemotePath,
        account: TransferAccount = None,
        blocking: Blocking = True,
        timeout: Timeout = None,
    ) -> dict:
        """Rename/move a file, directory, or symlink at the source_path to the
        target_path on system_name’s filesystem. This operation runs in a job.
        """
        account = load_config().checked_transfer(account, source_path, target_path)
        return self.client.mv(
            system_name,
            source_path=source_path,
            target_path=target_path,
            account=account,
            blocking=blocking,
            timeout=timeout,
        )

    @tool()
    def compress(
        self,
        system_name: SystemName,
        source_path: Annotated[str, "the absolute path of the file or directory"],
        target_path: Annotated[str, "the absolute path of the new archive"],
        dereference: Annotated[bool, "follow symbolic links"] = False,
        compression: Compression = "gzip",
        account: TransferAccount = None,
        blocking: Blocking = True,
    ) -> None:
        """Compress a directory or file."""
        account = load_config().checked_transfer(account, source_path, target_path)
        # match_pattern is left out: FirecREST puts it into a shell command without
        # escaping it.
        self.client.compress(
            system_name,
            source_path=source_path,
            target_path=target_path,
            dereference=dereference,
            compression=compression,
            account=account,
            blocking=blocking,
        )

    @tool()
    def extract(
        self,
        system_name: SystemName,
        source_path: Annotated[str, "the absolute path of the archive"],
        target_path: Annotated[str, "the absolute path of the target directory"],
        compression: Compression = "gzip",
        account: TransferAccount = None,
        blocking: Blocking = True,
    ) -> None:
        """Extract compressed archives."""
        account = load_config().checked_transfer(account, source_path, target_path)
        self.client.extract(
            system_name,
            source_path=source_path,
            target_path=target_path,
            compression=compression,
            account=account,
            blocking=blocking,
        )

    @tool()
    def cp(
        self,
        system_name: SystemName,
        source_path: RemotePath,
        target_path: RemotePath,
        dereference: Annotated[bool, "follow symbolic links"] = False,
        blocking: Blocking = True,
        account: TransferAccount = None,
        timeout: Timeout = None,
    ) -> dict:
        """Copy a file or a directory with its contents from source_path to
        target_path, replacing an existing target. This operation runs in a job.
        """
        account = load_config().checked_transfer(account, source_path, target_path)
        return self.client.cp(
            system_name,
            source_path=source_path,
            target_path=target_path,
            dereference=dereference,
            account=account,
            blocking=blocking,
            timeout=timeout,
        )

    @tool()
    def rm(
        self,
        system_name: SystemName,
        path: RemotePath,
        recursive: Annotated[
            bool, "must be true to delete a directory, which deletes everything in it"
        ] = False,
        account: TransferAccount = None,
        blocking: Blocking = True,
        timeout: Timeout = None,
    ) -> dict | None:
        """Delete a file, or a directory with everything in it if recursive is true.
        FirecREST first tries to delete it directly, and if that times out, it deletes
        it in a transfer job.
        """
        account = load_config().checked_transfer(account, path)
        # FirecREST always deletes a directory with everything in it, so a directory
        # needs recursive=True. With dereference=False, a symlink counts as a file,
        # and rm deletes the link, not what it points to.
        file_stat = self.client.stat(system_name, path=path, dereference=False)
        if S_ISDIR(file_stat["mode"]) and not recursive:
            raise ToolError(
                f"{path!r} is a directory. Pass recursive=True to delete it with"
                " everything in it."
            )
        return self.client.rm(
            system_name,
            path=path,
            account=account,
            blocking=blocking,
            timeout=timeout,
        )

    @tool()
    def upload(
        self,
        system_name: SystemName,
        local_file: Annotated[
            str,
            "the local path of the file, absolute or relative to the server's working"
            " directory",
        ],
        directory: Annotated[str, "the absolute path of the target directory"],
        filename: Annotated[str, "the name of the file in the target directory"],
        account: TransferAccount = None,
    ) -> dict | None:
        """Upload a file to the system and return when it has arrived. A file under
        the system's limit for direct uploads is uploaded in one request and None is
        returned. A larger file is moved by a transfer job, and the job's information
        is returned.
        """
        # FirecREST writes the file at the directory joined with the file name, so that
        # joined path is what is checked. posixpath.join drops the directory if the
        # file name starts with "/", and the directory would then go unchecked. An
        # empty file name would make the directory itself the target.
        if filename == "" or "/" in filename:
            raise ToolError(f"Filename {filename!r} must not be empty or contain '/'.")
        config = load_config()
        real_local_file = config.checked_local_path(local_file)
        account = config.checked_transfer(account, posixpath.join(directory, filename))
        self._use_direct_transfer_limit(system_name)
        transfer = self.client.upload(
            system_name,
            local_file=real_local_file,
            directory=directory,
            filename=filename,
            account=account,
            # With False, pyfirecrest leaves the transfer of a file too large for a
            # direct transfer unfinished. It returns an object to finish it with,
            # which this tool doesn't keep. See "External transfers" in
            # https://pyfirecrest.readthedocs.io/en/latest/tutorial_basic_v2.html
            blocking=True,
        )
        if transfer is None:
            return None
        # Only the job. The transfer directives hold signed URLs, which nothing here
        # uses.
        return transfer.transfer_data["transferJob"]

    @tool()
    def download(
        self,
        system_name: SystemName,
        source_path: RemotePath,
        target_path: Annotated[
            str,
            "the local path to save the file to, absolute or relative to the server's"
            " working directory",
        ],
        account: TransferAccount = None,
    ) -> dict | None:
        """Download a file from the system and return when it has arrived. A file
        under the system's limit for direct downloads is downloaded in one request and
        None is returned. A larger file is moved by a transfer job, and the job's
        information is returned.
        """
        config = load_config()
        real_target_path = config.checked_local_path(target_path)
        account = config.checked_transfer(account, source_path)
        self._use_direct_transfer_limit(system_name)
        transfer = self.client.download(
            system_name,
            source_path=source_path,
            target_path=real_target_path,
            account=account,
            # With False, pyfirecrest leaves the transfer of a file too large for a
            # direct transfer unfinished, as in upload.
            blocking=True,
        )
        if transfer is None:
            return None
        # Only the job. The transfer directives hold a signed URL, which nothing here
        # uses.
        return transfer.transfer_data["transferJob"]
