import logging
from importlib.metadata import metadata, version
from urllib.parse import urlsplit

import requests
from packaging.version import Version

logger = logging.getLogger(__name__)


def _get_pkg_name() -> str:
    return __name__.split(".")[0]


def _get_local_version() -> Version:
    return Version(version(_get_pkg_name()))


def _get_github_url() -> str | None:
    pkg_metadata = metadata(_get_pkg_name()).json

    project_urls = pkg_metadata.get("project_url")
    if not project_urls:
        logger.debug("Project metadata contains no URLs.")
        return

    for url in project_urls:
        key, value = url.split(", ")
        if key.lower() == "github":
            return value


def _get_upstream_version(github_url: str) -> Version:
    github_path = urlsplit(github_url).path
    owner, repo = github_path.removeprefix("/").removesuffix(".git").split("/")

    try:
        response = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/releases/latest",
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2026-03-10",
            },
            timeout=5,
        )
        response.raise_for_status()
    except requests.RequestException:
        logger.debug("Could not fetch latest release information from upstream.")
        raise

    upstream_tag = response.json()["tag_name"]

    # Raises InvalidVersion, a ValueError, for a tag that isn't a PEP 440 version.
    return Version(upstream_tag)


def get_server_metadata() -> tuple[Version, Version | None, str | None]:
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

    return local_version, upstream_version, github_url


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
