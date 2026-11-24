"""Tests for reading the config file and its account, group and local path
checks."""

from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError

from firecrest_mcp.config import (
    check_local_paths,
    cluster_name,
    load_cluster_config,
)


def test_missing_file_denies_everything(config):
    """Without a config file, nothing is allowed."""
    with pytest.raises(ToolError, match="does not exist"):
        load_cluster_config()
    with pytest.raises(ToolError, match="does not exist"):
        check_local_paths("data")


def test_unconfigured_cluster_denied(config):
    """A cluster without a table is denied."""
    config('[roihu]\nremote_paths = ["/scratch/project_1"]\n')
    with pytest.raises(ToolError, match=r"no \[lumi\] table"):
        load_cluster_config()


def test_clusters_are_separate(config, monkeypatch):
    """Each server reads only its own cluster's table."""
    config(
        '[lumi]\nremote_paths = ["/scratch/project_1"]\n'
        '[roihu]\nremote_paths = ["/scratch/project_2"]\n'
    )
    load_cluster_config().check_remote_paths("/scratch/project_1/file")
    monkeypatch.setenv("FIRECREST_URL", "https://api.roihu.csc.fi/v1")
    load_cluster_config().check_remote_paths("/scratch/project_2/file")
    with pytest.raises(ToolError, match="is not in remote_paths"):
        load_cluster_config().check_remote_paths("/scratch/project_1/file")


@pytest.mark.parametrize(
    ("url", "name"),
    [
        ("https://api.lumi.csc.fi/v1", "lumi"),
        ("https://api.roihu.csc.fi", "roihu"),
        ("http://localhost:8000/", "localhost"),
        ("https://firecrest.example.org/v2", "firecrest"),
    ],
)
def test_cluster_name(monkeypatch, url, name):
    """The cluster name is the first hostname label other than "api"."""
    monkeypatch.setenv("FIRECREST_URL", url)
    assert cluster_name() == name


@pytest.mark.parametrize("url", ["", "https://api/v1", "not a url"])
def test_cluster_name_underivable(monkeypatch, url):
    """A URL without a usable hostname is refused."""
    monkeypatch.setenv("FIRECREST_URL", url)
    with pytest.raises(ToolError, match="Cannot derive a cluster name"):
        cluster_name()


@pytest.mark.parametrize(
    ("content", "error"),
    [
        ("[lumi", "Expected ']'"),
        ("remote_paths = []", "remote_paths must be a table"),
        ("[lumi]\nremote_path = ['/p']", "lumi.remote_path: Extra inputs"),
        (
            "[lumi]\nremote_paths = '/p'",
            "lumi.remote_paths: Input should be a valid list",
        ),
        ("[lumi]\nremote_paths = ['results/']", "'results/' is not absolute"),
        ("[lumi]\nremote_paths = ['/s/../etc']", "'/s/../etc' must not contain '..'"),
        ("roihu = 1", "roihu must be a table"),
        ("[lumi.cpu]", "lumi.cpu: Extra inputs"),
        (
            "[lumi]\naccounts = ['p']\ndefault_account = 'q'",
            "default_account 'q' is not in accounts",
        ),
        (
            "[lumi]\ndefault_partition = 'small'",
            "default_partition 'small' is not in partitions",
        ),
    ],
)
def test_invalid_config_rejected(config, content, error):
    """Syntax errors, unknown keys, wrong types and stray defaults are reported."""
    config(content)
    with pytest.raises(ToolError, match=error):
        load_cluster_config()


@pytest.mark.parametrize(
    "url", ["https://api.lumi.csc.fi/v1", "https://api.roihu.csc.fi"]
)
def test_example_config_is_valid(config, monkeypatch, url):
    """examples/firecrest-mcp.toml loads for both clusters."""
    example = Path(__file__).parents[2] / "examples" / "firecrest-mcp.toml"
    config(example.read_text())
    monkeypatch.setenv("FIRECREST_URL", url)
    assert load_cluster_config().remote_paths


def test_changes_apply_without_reload(config):
    """Edits to the config file apply without a restart."""
    config('[lumi]\nremote_paths = ["/scratch/project_1/"]\n')
    load_cluster_config().check_remote_paths("/scratch/project_1/file")
    config('[lumi]\nremote_paths = ["/scratch/project_2/"]\n')
    with pytest.raises(ToolError, match="is not in remote_paths"):
        load_cluster_config().check_remote_paths("/scratch/project_1/file")


def test_account_defaults(config):
    """A missing account becomes the default; a given one must be allowed."""
    config()
    cluster = load_cluster_config()
    assert cluster.checked_account(None) == "project_1"
    assert cluster.checked_account("project_2") == "project_2"
    with pytest.raises(ToolError, match="Account 'project_3' is not in accounts"):
        cluster.checked_account("project_3")


def test_account_without_default_required(config):
    """Without default_account, an account must be given."""
    config('[lumi]\naccounts = ["project_1"]\n')
    with pytest.raises(ToolError, match="No account given"):
        load_cluster_config().checked_account(None)


def test_group(config):
    """Only listed groups are allowed, and a missing groups allows none."""
    config()
    load_cluster_config().check_group("project_1")
    for group in ["other", ""]:
        with pytest.raises(ToolError, match="is not in groups"):
            load_cluster_config().check_group(group)
    config("[lumi]\n")
    with pytest.raises(ToolError, match="is not in groups"):
        load_cluster_config().check_group("project_1")


@pytest.fixture
def local(config, tmp_path):
    """Default config with the local data directory created."""
    config()
    (tmp_path / "data").mkdir()


@pytest.mark.parametrize("path", ["data", "data/a/b", "./data/x", "/abs/local/f"])
def test_local_allowed(local, path):
    """Paths in or below local_paths pass; relative entries mean the server's
    working directory."""
    check_local_paths(path)


@pytest.mark.parametrize("path", [".", "other", "data/../other", "/abs", "/etc/x"])
def test_local_denied(local, path):
    """Paths outside local_paths are denied, '..' is resolved first."""
    with pytest.raises(ToolError, match="is not in local_paths"):
        check_local_paths(path)


def test_local_home_expanded(config, tmp_path, monkeypatch):
    """A "~" in local_paths and in paths means the home directory."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    config('local_paths = ["~/data"]\n')
    check_local_paths("~/data/x", tmp_path / "home" / "data" / "x")
    with pytest.raises(ToolError, match="is not in local_paths"):
        check_local_paths("~/other")


def test_local_symlink_resolved(local, tmp_path):
    """A symlink inside an allowed directory is checked by its target."""
    (tmp_path / "data" / "link").symlink_to("/etc")
    with pytest.raises(ToolError, match="is not in local_paths"):
        check_local_paths("data/link/passwd")


@pytest.mark.parametrize(
    "path",
    [".firecrest-mcp.toml", ".mcp.json", ".claude/x", ".git/hooks/x", "token"],
)
def test_local_protected(config, path):
    """Server and agent configuration and the token file are never allowed, even
    below local_paths. The config fixture puts the token file at "token" in the
    working directory."""
    config('local_paths = ["."]\n')
    with pytest.raises(ToolError, match="is protected"):
        check_local_paths(path)


def test_local_missing_key_denies_everything(config):
    """Without local_paths, no local path is allowed."""
    config("")
    with pytest.raises(ToolError, match="is not in local_paths"):
        check_local_paths("file")


@pytest.mark.parametrize("content", ["local_paths = 'data'", "local_paths = [1]"])
def test_local_paths_must_be_strings(config, content):
    """A local_paths that isn't a list of strings is a config error."""
    config(content)
    with pytest.raises(ToolError, match="local_paths must be a list of strings"):
        check_local_paths("data")


def test_local_paths_empty_entry(config):
    """An empty string in local_paths is a config error, so it can't allow the
    working directory by mistake."""
    config('local_paths = ["data", ""]\n')
    with pytest.raises(ToolError, match="must not contain an empty string"):
        check_local_paths("data")
