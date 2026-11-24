"""Tests for the remote path checks."""

import pytest
from fastmcp.exceptions import ToolError

from firecrest_mcp.config import load_config

# Unless a test writes its own config, the paths below are checked against the
# default CONFIG in conftest.py.


def check_remote_paths(*paths: str | None) -> None:
    load_config().check_remote_paths(*paths)


@pytest.mark.parametrize(
    "path",
    [
        "/scratch/project_1",
        "/scratch/project_1/a/b",
        "/scratch/project_1//a/./b",
        "/projappl/project_1/file",
    ],
)
def test_allowed(config, path):
    """Allowed directories and everything below them pass, even with // or /./."""
    config()
    check_remote_paths(path)


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/scratch",
        "/scratch/project_10",
        "/projappl/project_10/file",
        # PurePosixPath keeps a leading // as a separate root, so this path is not
        # below /scratch.
        "//scratch/project_1/file",
    ],
)
def test_denied(config, path):
    """Parents, siblings with a shared name prefix and paths that start with // are
    denied."""
    config()
    with pytest.raises(ToolError, match="is not in"):
        check_remote_paths(path)


@pytest.mark.parametrize(
    ("path", "error"),
    [
        ("scratch/project_1/file", "is not absolute"),
        ("~/file", "is not absolute"),
        ("/scratch/project_1/../project_2", "must not contain '..'"),
        ("/scratch/project_1/..", "must not contain '..'"),
        ("/scratch/project_1/x'; rm -rf ~; '", "must not contain quotes"),
        ("/scratch/project_1/x\ny", "control characters"),
    ],
)
def test_invalid_path_rejected(config, path, error):
    """Relative paths depend on the remote side, '..' is refused rather than
    resolved, and quotes and control characters could break out of the shell
    command FirecREST runs."""
    config()
    with pytest.raises(ToolError, match=error):
        check_remote_paths(path)


def test_dots_inside_names_allowed(config):
    """Only whole '..' components are refused, not dots in names."""
    config()
    check_remote_paths("/scratch/project_1/..hidden", "/scratch/project_1/a..b")


def test_other_special_characters_allowed(config):
    """Spaces, double quotes and other shell characters stay inside FirecREST's
    single quotes, so they are allowed."""
    config()
    check_remote_paths('/scratch/project_1/a b "c" $(d) ;&|')


@pytest.mark.parametrize(
    ("remote_paths", "path"),
    [
        pytest.param("[]", "/scratch/project_1/file", id="empty"),
        pytest.param(None, "/scratch/project_1/file", id="missing"),
        pytest.param('["/scratch/*"]', "/scratch/project_1/file", id="not-a-pattern"),
        pytest.param('["/project/project_1"]', "/projappl/project_2/x", id="alias"),
        pytest.param(
            '["/projapplx/project_1"]', "/projectx/project_1/f", id="alias-prefix"
        ),
    ],
)
def test_denied_by_config(config, remote_paths, path):
    """An empty or missing remote_paths allows nothing, entries are literal paths
    rather than patterns, and the LUMI alias maps only whole directories."""
    content = "[lumi]\n"
    if remote_paths is not None:
        content += f"remote_paths = {remote_paths}\n"
    config(content)
    with pytest.raises(ToolError, match="is not in remote_paths"):
        check_remote_paths(path)


def test_every_path_is_checked(config):
    """Every given path is checked, and None is skipped."""
    config()
    check_remote_paths("/scratch/project_1/a", None, "/projappl/project_1/b")
    with pytest.raises(ToolError, match="/etc/passwd"):
        check_remote_paths("/scratch/project_1/a", "/etc/passwd")


@pytest.mark.parametrize(
    ("entry", "path"),
    [
        ("/project/project_1", "/projappl/project_1/x"),
        ("/projappl/project_1", "/project/project_1/x"),
        ("/project/project_1", "/project//project_1/./x"),
    ],
)
def test_lumi_project_alias(config, entry, path):
    """On LUMI, /project and /projappl are the same directory."""
    config(f'[lumi]\nremote_paths = ["{entry}"]\n')
    check_remote_paths(path)


def test_project_alias_only_on_lumi(config, monkeypatch):
    """Other clusters have no aliases."""
    config('[roihu]\nremote_paths = ["/project/project_1"]\n')
    monkeypatch.setenv("FIRECREST_URL", "https://api.roihu.csc.fi/v1")
    with pytest.raises(ToolError, match="is not in remote_paths"):
        check_remote_paths("/projappl/project_1/x")
