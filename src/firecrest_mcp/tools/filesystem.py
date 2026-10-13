"""Tools for files on the system, and for uploading and downloading them."""

import pathlib
import posixpath
import re
from typing import Annotated

from fastmcp.exceptions import ToolError
from fastmcp.tools import tool
from firecrest.v2 import ExternalDownload, ExternalUpload, Firecrest

from firecrest_mcp.policy import check_local_paths, load_cluster
from firecrest_mcp.tools.params import (
    Account,
    Blocking,
    Compression,
    RemotePath,
    SystemName,
    Timeout,
)


class FirecrestFilesystemToolsMixin:
    client: Firecrest

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
        load_cluster().check_remote_paths(path)
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
        load_cluster().check_remote_paths(path)
        if first_lines is not None and last_lines is not None:
            raise ToolError("Give at most one of first_lines and last_lines.")
        if first_lines is not None:
            output = self.client.head(system_name, path=path, num_lines=first_lines)
        elif last_lines is not None:
            output = self.client.tail(system_name, path=path, num_lines=last_lines)
        else:
            return self.client.view(system_name, path=path)
        # head and tail also report positions, but only the text is of use here.
        return output["content"] if output else ""

    @tool()
    def checksum(self, system_name: SystemName, path: RemotePath) -> dict:
        """Calculate the SHA256 (256-bit) checksum of a specified file."""
        load_cluster().check_remote_paths(path)
        return self.client.checksum(system_name, path=path)

    @tool()
    def chmod(
        self,
        system_name: SystemName,
        path: RemotePath,
        mode: Annotated[str, "a numeric mode, as for chmod, e.g. 750"],
    ) -> dict:
        """Changes the file mod bits of a given file according to the specified mode."""
        load_cluster().check_remote_paths(path)
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
        cluster = load_cluster()
        cluster.check_remote_paths(path)
        cluster.check_group(group)
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
        load_cluster().check_remote_paths(path)
        return self.client.stat(system_name, path=path, dereference=dereference)

    @tool()
    def symlink(
        self,
        system_name: SystemName,
        source_path: Annotated[str, "the absolute path that the link points to"],
        link_path: Annotated[str, "the absolute path of the new link"],
    ) -> dict:
        """Create a symbolic link."""
        load_cluster().check_remote_paths(source_path, link_path)
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
        load_cluster().check_remote_paths(path)
        return self.client.mkdir(system_name, path=path, create_parents=create_parents)

    @tool()
    def mv(
        self,
        system_name: SystemName,
        source_path: RemotePath,
        target_path: RemotePath,
        account: Account = None,
        blocking: Blocking = True,
        timeout: Timeout = None,
    ) -> dict:
        """Rename/move a file, directory, or symlink at the source_path to the
        target_path on system_name’s filesystem. This operation runs in a job.
        """
        account = load_cluster().check_transfer(account, source_path, target_path)
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
        account: Account = None,
        blocking: Blocking = True,
    ) -> None:
        """Compress a directory or file."""
        account = load_cluster().check_transfer(account, source_path, target_path)
        # match_pattern is left out: FirecREST puts it into a shell command without
        # escaping it.
        return self.client.compress(
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
        account: Account = None,
        blocking: Blocking = True,
    ) -> None:
        """Extract compressed archives."""
        account = load_cluster().check_transfer(account, source_path, target_path)
        return self.client.extract(
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
        account: Account = None,
        timeout: Timeout = None,
    ) -> dict:
        """Copies file from source_path to target_path."""
        account = load_cluster().check_transfer(account, source_path, target_path)
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
        account: Account = None,
        blocking: Blocking = True,
        timeout: Timeout = None,
    ) -> dict | None:
        """Delete a file. FirecREST first tries to delete it directly, and if that
        times out, it deletes it in a transfer job.
        """
        account = load_cluster().check_transfer(account, path)
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
            str | pathlib.Path, "the local path of the file (can be relative)"
        ],
        directory: Annotated[str, "the absolute path of the target directory"],
        filename: Annotated[str, "the name of the file in the target directory"],
        account: Account = None,
        blocking: Blocking = True,
    ) -> ExternalUpload | None:
        """Upload a file to the system. Small files are uploaded directly and are
        available at once; None is returned. Large files are uploaded in parts to
        FirecREST's staging area and then moved to the target directory in a transfer
        job, whose information is returned.
        """
        check_local_paths(local_file)
        account = load_cluster().check_transfer(
            account, posixpath.join(directory, filename)
        )
        return self.client.upload(
            system_name,
            local_file=local_file,
            directory=directory,
            filename=filename,
            account=account,
            blocking=blocking,
        )

    @tool()
    def download(
        self,
        system_name: SystemName,
        source_path: RemotePath,
        target_path: Annotated[
            str | pathlib.Path, "the local path to save the file to (can be relative)"
        ],
        account: Account = None,
        blocking: Blocking = True,
    ) -> ExternalDownload | None:
        """Download a file from the remote system."""
        check_local_paths(target_path)
        account = load_cluster().check_transfer(account, source_path)
        return self.client.download(
            system_name,
            source_path=source_path,
            target_path=target_path,
            account=account,
            blocking=blocking,
        )
