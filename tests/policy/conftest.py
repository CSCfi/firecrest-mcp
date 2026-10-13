"""Fixtures that run the policy tests with a config file in a temporary directory."""

import pytest

# Sample config that the tests write unless they pass their own content.
CONFIG = """\
local_paths = ["data", "/abs/local"]

[lumi]
# Project directories
remote_paths = ["/scratch/project_1/", "/projappl/project_1"]
accounts = ["project_1", "project_2"]
default_account = "project_1"
partitions = ["small", "debug"]
default_partition = "small"
reservations = ["training"]
groups = ["project_1"]
"""


@pytest.fixture
def config(tmp_path, monkeypatch):
    """Run the test in an empty directory and return a function that writes the
    config file there, by default with the contents of CONFIG."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FIRECREST_URL", "https://api.lumi.csc.fi/v1")
    monkeypatch.setenv("FIRECREST_TOKEN_PATH", str(tmp_path / "token"))

    def write(content: str = CONFIG) -> None:
        (tmp_path / ".firecrest-mcp.toml").write_text(content)

    return write
