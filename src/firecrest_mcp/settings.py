"""The server's settings from the command line, which main() sets before it imports the
server. Tests set them with monkeypatch."""

from pathlib import Path

DEFAULT_TOKEN_FILE = "~/.firecrest-token"
# The project's config file, used when --config is not given. Relative to the working
# directory of the server process.
PROJECT_CONFIG_FILE = ".firecrest-mcp.toml"

# The URL of the cluster's FirecREST API, from --firecrest-url.
firecrest_url: str = ""
# The file that holds the FirecREST token, from --token-file, with "~" expanded.
token_file: Path = Path(DEFAULT_TOKEN_FILE).expanduser()
# The config file, from --config, with "~" expanded. A relative path is relative to
# the working directory.
config_file: Path = Path(PROJECT_CONFIG_FILE)
