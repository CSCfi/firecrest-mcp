"""The server's version and URL, and a check for a newer release on GitHub."""

import logging
from importlib.metadata import metadata, version
from typing import NamedTuple
from urllib.parse import urlsplit

import requests
from packaging.version import Version

logger = logging.getLogger(__name__)

# The distribution name in pyproject.toml.
PACKAGE_NAME = "firecrest-mcp"


class ServerMetadata(NamedTuple):
    local_version: Version
    # None when the project has no GitHub URL or the check failed.
    upstream_version: Version | None
    github_url: str | None


def _get_local_version() -> Version:
    return Version(version(PACKAGE_NAME))


def _get_github_url() -> str | None:
    pkg_metadata = metadata(PACKAGE_NAME).json

    project_urls = pkg_metadata.get("project_url")
    if not project_urls:
        logger.debug("Project metadata contains no URLs.")
        return

    # Each entry is "label, URL". Splitting at the first comma keeps a URL that
    # contains a comma whole.
    for entry in project_urls:
        label, _, url = entry.partition(",")
        label = label.strip()
        url = url.strip()
        if label.lower() == "github" and url:
            return url


def _get_upstream_version(github_url: str) -> Version:
    github_path = urlsplit(github_url).path
    owner, repo = github_path.removeprefix("/").removesuffix(".git").split("/")

    response = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}/releases/latest",
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10",
        },
        timeout=5,
    )
    response.raise_for_status()

    upstream_tag = response.json()["tag_name"]

    # Raises InvalidVersion, a ValueError, for a tag that isn't a PEP 440 version.
    return Version(upstream_tag)


def get_server_metadata() -> ServerMetadata:
    """Return the installed version, the GitHub URL and the latest release on GitHub.

    It requests the latest release from the GitHub API when the project metadata
    has a GitHub URL. A failed request is logged and gives no upstream version.
    """
    local_version = _get_local_version()

    upstream_version = None
    github_url = _get_github_url()

    if github_url:
        try:
            upstream_version = _get_upstream_version(github_url)
        except (requests.RequestException, KeyError, ValueError):
            logger.debug("Could not check upstream version.", exc_info=True)
    else:
        logger.debug("Project has no GitHub URL.")

    return ServerMetadata(
        local_version=local_version,
        upstream_version=upstream_version,
        github_url=github_url,
    )


def get_update_message(
    local_version: Version, upstream_version: Version | None
) -> str | None:
    """Return a hint to upgrade when the upstream version is newer than the local
    one, and None otherwise.
    """
    if upstream_version is None:
        return
    if local_version < upstream_version:
        return (
            "A newer version of FirecREST MCP is available. "
            "It is recommended to upgrade the package. "
            f"({local_version} -> {upstream_version})"
        )
