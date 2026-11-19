import logging
import re
from importlib.metadata import metadata, version
from urllib.parse import urlsplit

import requests

logger = logging.getLogger(__name__)

# https://semver.org/#is-there-a-suggested-regular-expression-regex-to-check-a-semver-string
SEMVER_RE = (
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    + r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    + r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    + r"(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)


def _get_pkg_name() -> str:
    return __name__.split(".")[0]


def _get_local_version() -> str:
    return version(_get_pkg_name())


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


def _get_upstream_version(github_url: str) -> str:
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

    upstream_semver_match = re.search(SEMVER_RE, upstream_tag.removeprefix("v"))
    if not upstream_semver_match:
        raise ValueError(
            f"Failed to parse SemVer version number from upstream tag '{upstream_tag}'."
        )

    return upstream_semver_match.group(0)


def get_server_metadata() -> tuple[str, str | None, str | None]:
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
