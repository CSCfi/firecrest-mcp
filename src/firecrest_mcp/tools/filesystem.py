import pathlib
from typing import Annotated, Any

from fastmcp.tools import tool
from firecrest.v2 import ExternalDownload, ExternalUpload


class FirecrestFilesystemToolsMixin:
    @tool()
    def list_files(
        self,
        system_name: Annotated[str, "the system name where the filesystem belongs to"],
        path: Annotated[str, "the absolute target path"],
        show_hidden: Annotated[bool, "Show hidden files"] = False,
        recursive: Annotated[bool, "recursively list directories encountered"] = False,
        numeric_uid: Annotated[bool, "list numeric user and group IDs"] = False,
        dereference: Annotated[
            bool,
            "when showing file information for a symbolic link, show information for"
            + " the file the link references rather than for the link itself",
        ] = False,
    ) -> list[dict]:
        """Returns a list of files in a directory."""
        return self.client.list_files(
            system_name,
            path,
            show_hidden,
            recursive,
            numeric_uid,
            dereference,
        )

    @tool()
    def head(
        self,
        system_name: Annotated[str, "the system name where the filesystem belongs to"],
        path: Annotated[str, "the absolute target path of the file"],
        num_bytes: Annotated[
            int | None, "the output will be the first NUM bytes of each file"
        ] = None,
        num_lines: Annotated[
            int | None, "the output will be the first NUM lines of each file"
        ] = None,
        exclude_trailing: Annotated[
            bool,
            "the output will be the whole file, without the last NUM bytes/lines of"
            + " each file. NUM should be specified in the respective argument through"
            + " num_bytes or num_lines.",
        ] = False,
    ) -> dict:
        """Display the beginning of a specified file. By default 10 lines will be
        returned. num_bytes and num_lines cannot be specified simultaneously.
        """
        return self.client.head(
            system_name, path, num_bytes, num_lines, exclude_trailing
        )

    @tool()
    def tail(
        self,
        system_name: Annotated[str, "the system name where the filesystem belongs to"],
        path: Annotated[str, "the absolute target path of the file"],
        num_bytes: Annotated[
            int | None, "The output will be the last NUM bytes of each file"
        ] = None,
        num_lines: Annotated[
            int | None, "The output will be the last NUM lines of each file"
        ] = None,
        exclude_beginning: Annotated[
            bool,
            "The output will be the whole file, without the first NUM bytes/lines of"
            + " each file. NUM should be specified in the respective argument through"
            + " num_bytes or num_lines.",
        ] = False,
    ) -> dict:
        """Display the ending of a specified file. By default, 10 lines will be
        returned. num_bytes and num_lines cannot be specified simultaneously.
        """
        return self.client.tail(
            system_name, path, num_bytes, num_lines, exclude_beginning
        )

    @tool()
    def view(
        self,
        system_name: Annotated[str, "the system name where the filesystem belongs to"],
        path: Annotated[str, "the absolute target path of the file"],
    ) -> str:
        """View full file content (up to 5MB files)"""
        return self.client.view(system_name, path)

    @tool()
    def checksum(
        self,
        system_name: Annotated[str, "the system name where the filesystem belongs to"],
        path: Annotated[str, "the absolute target path of the file"],
    ) -> dict:
        """Calculate the SHA256 (256-bit) checksum of a specified file."""
        return self.client.checksum(system_name, path)

    @tool()
    def file_type(
        self,
        system_name: Annotated[str, "the system name where the filesystem belongs to"],
        path: Annotated[str, "the absolute target path of the file"],
    ) -> str:
        """Uses the file linux application to determine the type of a file."""
        return self.client.file_type(system_name, path)

    @tool()
    def chmod(
        self,
        system_name: Annotated[str, "the system name where the filesystem belongs to"],
        path: Annotated[str, "the absolute target path of the file"],
        mode: Annotated[str, "same as numeric mode of linux chmod tool"],
    ) -> dict:
        """Changes the file mod bits of a given file according to the specified mode."""
        return self.client.chmod(system_name, path, mode)

    @tool()
    def chown(
        self,
        system_name: Annotated[str, "the system name where the filesystem belongs to"],
        path: Annotated[str, "the absolute target path of the file"],
        owner: Annotated[str, "owner ID for target"],
        group: Annotated[str, "group ID for target"],
    ) -> dict:
        """Changes the user and/or group ownership of a given file. If only owner or
        group information is passed, only that information will be updated.
        """
        return self.client.chown(system_name, path, owner, group)

    @tool()
    def stat(
        self,
        system_name: Annotated[str, "the system name where the filesystem belongs to"],
        path: Annotated[str, "the absolute target path of the file"],
        dereference: Annotated[bool, "follow symbolic links"] = False,
    ) -> dict:
        """Uses the stat linux application to determine the status of a file on the
        system's filesystem. The result follows:
        https://docs.python.org/3/library/os.html#os.stat_result.
        """
        return self.client.stat(system_name, path, dereference)

    @tool()
    def symlink(
        self,
        system_name: Annotated[str, "the system name where the filesystem belongs to"],
        source_path: Annotated[str, "the absolute path to the file the link points to"],
        link_path: Annotated[str, "the absolute path to the symlink"],
    ) -> dict:
        """Create a symbolic link."""
        return self.client.symlink(system_name, source_path, link_path)

    @tool()
    def mkdir(
        self,
        system_name: Annotated[str, "the system name where the filesystem belongs to"],
        path: Annotated[str, "the absolute target path to the new directory"],
        create_parents: Annotated[
            bool, "create intermediate parent directories"
        ] = False,
    ) -> dict:
        """Create a directory."""
        return self.client.mkdir(system_name, path, create_parents)

    @tool()
    def mv(
        self,
        system_name: Annotated[str, "the system name where the filesystem belongs to"],
        source_path: Annotated[str, "the absolute source path"],
        target_path: Annotated[str, "the absolute target path"],
        account: Annotated[
            str | None, "the account to be used for the transfer job"
        ] = None,
        blocking: Annotated[bool, "whether to wait dor the job to complete"] = True,
        timeout: Annotated[
            float | None, "the maximum time to wait for the job to complete"
        ] = None,
    ) -> dict:
        """Rename/move a file, directory, or symlink at the source_path to the
        target_path on system_name’s filesystem. This operation runs in a job.
        """
        return self.client.mv(
            system_name, source_path, target_path, account, blocking, timeout
        )

    @tool()
    def compress(
        self,
        system_name: Annotated[str, "the system name where the filesystem belongs to"],
        source_path: Annotated[str, "the absolute path to the source directory"],
        target_path: Annotated[
            str, "the absolute path to the newly created compressed file"
        ],
        dereference: Annotated[bool, "dereference links when compressing"] = False,
        compression: Annotated[
            str,
            "compression algorithm to use (one of 'none', 'gzip', 'bzip2', 'xz')."
            + " Default is 'gzip'.",
        ] = "gzip",
        match_pattern: Annotated[
            str | None, "regex pattern to filter files to compress"
        ] = None,
        account: Annotated[
            str | None,
            "the account to be used for the transfer job (only relevant when the"
            + " compression operation is not done directly)",
        ] = None,
        blocking: Annotated[
            bool,
            "whether to wait dor the job to complete (only relevant when the"
            + " compression operation is not done directly)",
        ] = True,
    ) -> None:
        """Compress a directory or file."""
        return self.client.compress(
            system_name,
            source_path,
            target_path,
            dereference,
            compression,
            match_pattern,
            account,
            blocking,
        )

    @tool()
    def extract(
        self,
        system_name: Annotated[str, "the system name where the filesystem belongs to"],
        source_path: Annotated[str, "the absolute path to the archive"],
        target_path: Annotated[str, "the absolute path to target directory"],
        compression: Annotated[
            str,
            "compression algorithm to use (one of 'none', 'gzip', 'bzip2', 'xz')."
            + " Default is 'gzip'.",
        ] = "gzip",
        account: Annotated[
            str | None,
            "the account to be used for the transfer job (only relevant when the"
            + " extract operation is not done directly)",
        ] = None,
        blocking: Annotated[
            bool,
            "whether to wait dor the job to complete (only relevant when the extract"
            + " operation is not done directly)",
        ] = True,
    ) -> None:
        """Extract compressed archives."""
        return self.client.extract(
            system_name, source_path, target_path, compression, account, blocking
        )

    @tool()
    def wait_for_job(
        self,
        system_name: Annotated[str, "the system name where the filesystem belongs to"],
        jobid: Annotated[str | None, "the ID of the job"] = None,
        timeout: Annotated[
            float | None, "the maximum time to wait for the job to complete"
        ] = None,
        not_found_timeout: Annotated[
            float,
            "the maximum time to wait for the job to be available in the scheduler, in"
            + " seconds. Slurm or other scheduler will need a few seconds before"
            + " updating the database. If the job is not found within this time, the"
            + " function will raise an exception.",
        ] = 20.0,
    ) -> list[Any]:
        """Wait for a job to complete. When the job is completed, it will return the job
        information.
        """
        return self.client.wait_for_job(system_name, jobid, timeout, not_found_timeout)

    @tool()
    def cp(
        self,
        system_name: Annotated[str, "the system name where the filesystem belongs to"],
        source_path: Annotated[str, "the absolute source path"],
        target_path: Annotated[str, "the absolute target path"],
        dereference: Annotated[bool, "dereference links when copying"] = False,
        blocking: Annotated[bool, "whether to wait dor the job to complete"] = True,
        account: Annotated[
            str | None, "the account to be used for the transfer job"
        ] = None,
        timeout: Annotated[
            float | None, "the maximum time to wait for the job to complete"
        ] = None,
    ) -> dict:
        """Copies file from source_path to target_path."""
        return self.client.cp(
            system_name,
            source_path,
            target_path,
            dereference,
            blocking,
            account,
            timeout,
        )

    @tool()
    def rm(
        self,
        system_name: Annotated[str, "the system name where the filesystem belongs to"],
        path: Annotated[str, "the absolute target path"],
        account: Annotated[
            str | None,
            "the account to be used for the transfer job (only relevant when the file"
            + "is not deleted directly)",
        ] = None,
        blocking: Annotated[
            bool,
            "whether to wait dor the job to complete (only relevant when the file is"
            + "not deleted directly)",
        ] = True,
        timeout: Annotated[
            float | None, "the maximum time to wait for the job to complete"
        ] = None,
    ) -> dict | None:
        """Delete a file. First the self.client will try to delete the file directly,
        and if it fails with a timeout, it will launch a job to delete the file.
        """
        return self.client.rm(system_name, path, account, blocking, timeout)

    @tool()
    def upload(
        self,
        system_name: Annotated[str, "the system name where the filesystem belongs to"],
        local_file: Annotated[
            str | pathlib.Path,
            "the local file’s path to be uploaded (can be relative)"
            + "or a file-like object (implements .read())",
        ],
        directory: Annotated[
            str,
            "the absolut target path of the directory where the file will be uploaded",
        ],
        filename: Annotated[str, "the name of the file in the target directory"],
        account: Annotated[
            str | None,
            "the account to be used for the transfer job (only relevant when the file"
            + "is larger than MAX_DIRECT_UPLOAD_SIZE)",
        ] = None,
        blocking: Annotated[
            bool,
            "whether to wait dor the job to complete (only relevant when the file is"
            + " larger than MAX_DIRECT_UPLOAD_SIZE)",
        ] = True,
        transfer_method: Annotated[
            str,
            "the method to be used for the upload of large files. Supported methods:"
            + " 's3', 'streamer', 'wormhole'.",
        ] = "s3",
        file_size: Annotated[
            int | None,
            "the size of the file in bytes. Required for the local_file is a file-like"
            + " object.",
        ] = None,
    ) -> ExternalUpload | None:
        """Upload a file to the system. Small files will be uploaded directly to
        FirecREST and will be immediately available. The function will return None in
        this case. Large files will be uploaded in parts to the staging area of
        FirecREST and then moved to the target directory in a job. The function will
        return the transfer job information in this case.
        """
        return self.client.upload(
            system_name,
            local_file,
            directory,
            filename,
            account,
            blocking,
            transfer_method,
            file_size,
        )

    @tool()
    def download(
        self,
        system_name: Annotated[str, "the system name where the filesystem belongs to"],
        source_path: Annotated[str, "the absolute source path of the file"],
        target_path: Annotated[
            str | pathlib.Path,
            "the target path in the local filesystem (can be relative path)",
        ],
        account: Annotated[
            str | None,
            "the account to be used for the transfer job (only relevant when the file"
            + "is larger than MAX_DIRECT_UPLOAD_SIZE)",
        ] = None,
        blocking: Annotated[bool, "whether to wait dor the job to complete"] = True,
        transfer_method: Annotated[
            str,
            "the method to be used for the upload of large files. Supported methods:"
            + " 's3', 'streamer', 'wormhole'.",
        ] = "s3",
    ) -> ExternalDownload:
        """Download a file from the remote system."""
        return self.client.download(
            system_name,
            source_path,
            target_path,
            account,
            blocking,
            transfer_method,
        )
