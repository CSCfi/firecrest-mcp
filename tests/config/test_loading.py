"""Tests for reading the config file and its account, group and local path
checks."""

import re
from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError

from firecrest_mcp.config import cluster_name, load_config


def test_missing_file_denies_everything(config):
    """Without a config file, nothing is allowed."""
    with pytest.raises(ToolError, match="does not exist"):
        load_config()


def test_unconfigured_cluster_denied(config):
    """A cluster without a table is denied."""
    config('[roihu]\nremote_paths = ["/scratch/project_1"]\n')
    with pytest.raises(ToolError, match=r"no \[lumi\] table"):
        load_config()


def test_clusters_are_separate(config, monkeypatch):
    """Each server reads only its own cluster's table."""
    config(
        '[lumi]\nremote_paths = ["/scratch/project_1"]\n'
        '[roihu]\nremote_paths = ["/scratch/project_2"]\n'
    )
    load_config().check_remote_paths("/scratch/project_1/file")
    monkeypatch.setenv("FIRECREST_URL", "https://api.roihu.csc.fi/v1")
    load_config().check_remote_paths("/scratch/project_2/file")
    with pytest.raises(ToolError, match="is not in remote_paths"):
        load_config().check_remote_paths("/scratch/project_1/file")


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
            "[lumi]\nlocal_paths = ['data']",
            r"local_paths must be a top-level key, not in \[lumi\]",
        ),
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
        load_config()


@pytest.mark.parametrize(
    "url", ["https://api.lumi.csc.fi/v1", "https://api.roihu.csc.fi"]
)
def test_example_config_is_valid(config, monkeypatch, url):
    """examples/firecrest-mcp.toml loads for both clusters."""
    example = Path(__file__).parents[2] / "examples" / "firecrest-mcp.toml"
    config(example.read_text())
    monkeypatch.setenv("FIRECREST_URL", url)
    assert load_config().remote_paths


def test_changes_apply_without_reload(config):
    """Edits to the config file apply without a restart."""
    config('[lumi]\nremote_paths = ["/scratch/project_1/"]\n')
    load_config().check_remote_paths("/scratch/project_1/file")
    config('[lumi]\nremote_paths = ["/scratch/project_2/"]\n')
    with pytest.raises(ToolError, match="is not in remote_paths"):
        load_config().check_remote_paths("/scratch/project_1/file")


def test_account_defaults(config):
    """A missing account becomes the default; a given one must be allowed."""
    config()
    assert load_config().checked_account(None) == "project_1"
    assert load_config().checked_account("project_2") == "project_2"
    with pytest.raises(ToolError, match="Account 'project_3' is not in accounts"):
        load_config().checked_account("project_3")


def test_account_without_default_required(config):
    """Without default_account, an account must be given."""
    config('[lumi]\naccounts = ["project_1"]\n')
    with pytest.raises(ToolError, match="No account given"):
        load_config().checked_account(None)


def test_group(config):
    """Only listed groups are allowed, and a missing groups allows none."""
    config()
    load_config().check_group("project_1")
    for group in ["other", ""]:
        with pytest.raises(ToolError, match="is not in groups"):
            load_config().check_group(group)
    config("[lumi]\n")
    with pytest.raises(ToolError, match="is not in groups"):
        load_config().check_group("project_1")


@pytest.fixture
def local(config, tmp_path):
    """Default config with the local data directory created."""
    config()
    (tmp_path / "data").mkdir()


@pytest.mark.parametrize("path", ["data", "data/a/b", "./data/x", "/abs/local/f"])
def test_local_allowed(local, path):
    """Paths in or below local_paths pass; relative entries mean the server's
    working directory."""
    load_config().checked_local_path(path)


@pytest.mark.parametrize("path", [".", "other", "data/../other", "/abs", "/etc/x"])
def test_local_denied(local, path):
    """Paths outside local_paths are denied, '..' is resolved first."""
    with pytest.raises(ToolError, match="is not in local_paths"):
        load_config().checked_local_path(path)


def test_local_home_expanded(config, tmp_path, monkeypatch):
    """A "~" in local_paths and in paths means the home directory."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    config('local_paths = ["~/data"]\n[lumi]\n')
    real_path = tmp_path / "home" / "data" / "x"
    assert load_config().checked_local_path("~/data/x") == real_path
    assert load_config().checked_local_path(str(real_path)) == real_path
    with pytest.raises(ToolError, match="is not in local_paths"):
        load_config().checked_local_path("~/other")


def test_local_symlink_resolved(local, tmp_path):
    """A symlink inside an allowed directory is checked by its target."""
    (tmp_path / "data" / "link").symlink_to("/etc")
    with pytest.raises(ToolError, match="is not in local_paths"):
        load_config().checked_local_path("data/link/passwd")


@pytest.mark.parametrize(
    "path",
    [".firecrest-mcp.toml", ".mcp.json", ".claude/x", ".git/hooks/x", "token"],
)
def test_local_protected(config, path):
    """Server and agent configuration and the token file are never allowed, even
    below local_paths. The config fixture puts the token file at "token" in the
    working directory."""
    config('local_paths = ["."]\n[lumi]\n')
    with pytest.raises(ToolError, match="is protected"):
        load_config().checked_local_path(path)


@pytest.mark.parametrize("protected", ["token", ".firecrest-mcp.toml"])
def test_local_hard_link_to_protected_file(local, tmp_path, protected):
    """A hard link below local_paths to a protected file is refused, because it is
    the same file under another name."""
    (tmp_path / "token").write_text("token")
    (tmp_path / "data" / "link").hardlink_to(tmp_path / protected)
    with pytest.raises(ToolError, match="is protected"):
        load_config().checked_local_path("data/link")


def is_case_insensitive(directory: Path) -> bool:
    """Return whether the file system of a directory ignores the case of names."""
    probe = directory / "probe"
    probe.write_text("")
    insensitive = (directory / "PROBE").exists()
    probe.unlink()
    return insensitive


def test_local_protected_in_other_case(config, tmp_path):
    """On a file system that ignores case, such as macOS's default, another spelling
    of a protected file is the same file and is refused."""
    if not is_case_insensitive(tmp_path):
        pytest.skip("the file system is case-sensitive")
    config('local_paths = ["."]\n[lumi]\n')
    with pytest.raises(ToolError, match="is protected"):
        load_config().checked_local_path(".FIRECREST-MCP.TOML")


@pytest.mark.parametrize("entry", ["work", "work/sub"])
def test_local_entry_with_symlink_refused(config, tmp_path, entry):
    """An entry with a symlink in its path is refused, and the error names the real
    path to list instead. Otherwise changing the link would change which
    directory is allowed."""
    config(f'local_paths = ["{entry}"]\n[lumi]\n')
    (tmp_path / "elsewhere" / "sub").mkdir(parents=True)
    (tmp_path / "work").symlink_to(tmp_path / "elsewhere")
    real_path = (tmp_path / entry).resolve()
    with pytest.raises(ToolError, match=re.escape(str(real_path))):
        load_config().checked_local_path(f"{entry}/x")


def test_local_missing_key_denies_everything(config):
    """Without local_paths, no local path is allowed."""
    config("[lumi]\n")
    with pytest.raises(ToolError, match="is not in local_paths"):
        load_config().checked_local_path("file")


@pytest.mark.parametrize(
    ("content", "error"),
    [
        ("local_paths = 'data'", "local_paths: Input should be a valid list"),
        ("local_paths = [1]", r"local_paths\.0: Input should be a valid string"),
    ],
)
def test_local_paths_must_be_strings(config, content, error):
    """A local_paths that isn't a list of strings is a config error."""
    config(content + "\n[lumi]\n")
    with pytest.raises(ToolError, match=error):
        load_config().checked_local_path("data")


def test_local_paths_empty_entry(config):
    """An empty string in local_paths is a config error, so it can't allow the
    working directory by mistake."""
    config('local_paths = ["data", ""]\n[lumi]\n')
    with pytest.raises(
        ToolError, match=r"local_paths\.1: .*must not be an empty string"
    ):
        load_config().checked_local_path("data")
