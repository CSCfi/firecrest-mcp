"""Tests for the update check in metadata.py, with the package metadata and the
GitHub API mocked."""

from unittest.mock import Mock

import pytest
import requests
from packaging.version import Version

from firecrest_mcp import metadata


def release_response(tag: str) -> Mock:
    """Return a mock response of the GitHub API for a latest release with this tag."""
    response = Mock()
    response.json.return_value = {"tag_name": tag}
    return response


@pytest.fixture
def set_project_urls(monkeypatch):
    """Return a function that sets the Project-URL entries of the package metadata,
    each as "label, URL"."""

    def set_urls(entries: list[str]) -> None:
        # The JSON form of the metadata leaves out project_url when there are no
        # entries.
        pkg_metadata_json = {}
        if entries:
            pkg_metadata_json["project_url"] = entries
        pkg_metadata = Mock(json=pkg_metadata_json)
        monkeypatch.setattr(metadata, "metadata", Mock(return_value=pkg_metadata))

    return set_urls


@pytest.fixture
def github_get(monkeypatch) -> Mock:
    """Replace requests.get in the metadata module and return the mock."""
    get = Mock()
    monkeypatch.setattr(metadata.requests, "get", get)
    return get


@pytest.mark.parametrize(
    "entries",
    [
        [],
        ["Homepage, https://example.org"],
        ["GitHub"],
        ["GitHub, "],
    ],
    ids=["no entries", "no GitHub label", "no comma", "empty URL"],
)
def test_no_github_url(set_project_urls, github_get, entries):
    """Without a GitHub entry that has a URL, no request is made and there is no
    upstream version."""
    set_project_urls(entries)

    server_metadata = metadata.get_server_metadata()

    assert server_metadata.github_url is None
    assert server_metadata.upstream_version is None
    github_get.assert_not_called()


def test_request(set_project_urls, github_get):
    """The latest release is requested for the owner and repository in the GitHub
    URL, without its .git suffix, and its tag becomes the upstream version."""
    set_project_urls(
        ["Homepage, https://example.org", "GitHub, https://github.com/owner/repo.git"]
    )
    github_get.return_value = release_response("v1.2.3")

    server_metadata = metadata.get_server_metadata()

    assert server_metadata.github_url == "https://github.com/owner/repo.git"
    assert server_metadata.upstream_version == Version("1.2.3")
    github_get.assert_called_once()
    assert github_get.call_args.args == (
        "https://api.github.com/repos/owner/repo/releases/latest",
    )


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("1.2.3", Version("1.2.3")),
        ("v1.2.3", Version("1.2.3")),
        ("1.2.3-rc.1", Version("1.2.3rc1")),
        # Valid SemVer, but not a PEP 440 version.
        ("v1.0.0-alpha.beta", None),
        ("release-1", None),
    ],
)
def test_tag(set_project_urls, github_get, tag, expected):
    """A tag that packaging can parse becomes the upstream version, with or without
    a leading v. Any other tag gives no upstream version."""
    set_project_urls(["GitHub, https://github.com/owner/repo"])
    github_get.return_value = release_response(tag)

    assert metadata.get_server_metadata().upstream_version == expected


@pytest.mark.parametrize(
    "error",
    [requests.ConnectionError("refused"), requests.Timeout("timed out")],
    ids=["connection error", "timeout"],
)
def test_request_error(set_project_urls, github_get, error):
    """A request that fails gives no upstream version."""
    set_project_urls(["GitHub, https://github.com/owner/repo"])
    github_get.side_effect = error

    assert metadata.get_server_metadata().upstream_version is None


def http_error_response() -> Mock:
    response = Mock()
    response.raise_for_status.side_effect = requests.HTTPError("403 rate limited")
    return response


def no_tag_response() -> Mock:
    response = Mock()
    response.json.return_value = {}
    return response


def not_json_response() -> Mock:
    response = Mock()
    response.json.side_effect = requests.JSONDecodeError("Expecting value", "", 0)
    return response


@pytest.mark.parametrize(
    "response",
    [http_error_response(), no_tag_response(), not_json_response()],
    ids=["HTTP error", "no tag_name", "not JSON"],
)
def test_bad_response(set_project_urls, github_get, response):
    """An HTTP error status or a body without a tag gives no upstream version."""
    set_project_urls(["GitHub, https://github.com/owner/repo"])
    github_get.return_value = response

    assert metadata.get_server_metadata().upstream_version is None


def test_github_url_not_a_repository(set_project_urls, github_get):
    """A GitHub URL whose path isn't /owner/repo gives no upstream version and no
    request."""
    set_project_urls(["GitHub, https://github.com/owner/repo/tree/main"])

    server_metadata = metadata.get_server_metadata()

    assert server_metadata.github_url == "https://github.com/owner/repo/tree/main"
    assert server_metadata.upstream_version is None
    github_get.assert_not_called()


@pytest.mark.parametrize(
    "upstream_version",
    [Version("1.0.0"), Version("0.9.0"), Version("1.0.0rc1"), None],
    ids=["equal", "older", "older prerelease", "missing"],
)
def test_no_update_message(upstream_version):
    """There is no message unless the upstream version is newer."""
    assert metadata.get_update_message(Version("1.0.0"), upstream_version) is None


def test_update_message():
    """A newer upstream version gives a message that names both versions."""
    message = metadata.get_update_message(Version("1.0.0"), Version("1.1.0rc1"))

    assert message is not None
    assert "(1.0.0 -> 1.1.0rc1)" in message
