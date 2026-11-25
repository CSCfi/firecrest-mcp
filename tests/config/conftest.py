"""Fixtures that run the config tests with a config file in a temporary directory and
give the tools a mock FirecREST client."""

from pathlib import Path
from unittest.mock import create_autospec

import pytest
from firecrest.v2 import Firecrest

from firecrest_mcp import settings
from firecrest_mcp.tools.compute import _user_name

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
    monkeypatch.setattr(settings, "firecrest_url", "https://api.lumi.csc.fi/v1")
    monkeypatch.setattr(settings, "token_file", tmp_path / "token")
    monkeypatch.setattr(settings, "config_file", Path(settings.PROJECT_CONFIG_FILE))

    def write(content: str = CONFIG) -> None:
        (tmp_path / ".firecrest-mcp.toml").write_text(content)

    return write


# Building the mock takes about 40 ms, so all tests share one instead of building
# one each.
@pytest.fixture(scope="session")
def firecrest_autospec():
    """A mock FirecREST client with the client's signatures, built once."""
    return create_autospec(Firecrest, instance=True)


@pytest.fixture
def mock_client(firecrest_autospec):
    """The shared mock client, cleared of what earlier tests did with it."""
    # Forget the calls, return values and side effects that earlier tests set.
    firecrest_autospec.reset_mock(return_value=True, side_effect=True)
    # _user_name caches the user's name per client. With one shared client, the name
    # an earlier test fetched would be returned without calling userinfo.
    _user_name.cache_clear()
    return firecrest_autospec
