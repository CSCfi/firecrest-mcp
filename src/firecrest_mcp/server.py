import os
import time
from pathlib import Path

import jwt
from fastmcp import FastMCP
from firecrest.v2 import Firecrest

from firecrest_mcp.tools.compute import FirecrestComputeToolsMixin
from firecrest_mcp.tools.filesystem import FirecrestFilesystemToolsMixin
from firecrest_mcp.tools.status import FirecrestStatusToolsMixin


class TokenAuth:
    def __init__(self):
        pass

    def _is_token_valid(self, token: str) -> bool:
        try:
            payload = jwt.decode(
                token,
                options={
                    "verify_signature": False,
                    "verify_exp": False,
                    "verify_aud": False,
                },
            )
            return time.time() <= payload["exp"]
        except Exception:
            return False

    def get_access_token(self):
        path = Path(
            os.getenv("FIRECREST_TOKEN_PATH", "~/.firecrest/token")
        ).expanduser()
        try:
            # Refuse the file if group or others have any permission bits set
            # (same rule as SSH private keys).
            if path.stat().st_mode & 0o077:
                raise RuntimeError(
                    f"Token file {path} is accessible by other users. "
                    f"Run `chmod 600 {path}` to fix this."
                )
            token = path.read_text().strip()
        except OSError as e:
            raise RuntimeError(f"Could not read token file {path}: {e}") from e
        if not token:
            raise RuntimeError(f"Token file {path} is empty.")
        if not self._is_token_valid(token):
            raise RuntimeError("Token is invalid or has expired.")
        return token


class FirecrestClientWrapper(
    FirecrestComputeToolsMixin,
    FirecrestFilesystemToolsMixin,
    FirecrestStatusToolsMixin,
):
    def __init__(self, url: str):
        self.client = Firecrest(
            firecrest_url=url,
            authorization=TokenAuth(),
        )


url = os.getenv("FIRECREST_URL", None)
if not url:
    raise RuntimeError("Environment variable FIRECREST_URL is not defined.")

fc = FirecrestClientWrapper(url)
CONTEXT_DIR = Path(__file__).parent / "context"
instructions = None
if "roihu" in url:
    instructions = (CONTEXT_DIR / "roihu.md").read_text()
elif "lumi" in url:
    instructions = (CONTEXT_DIR / "lumi.md").read_text()

mcp = FastMCP("FirecREST v2", instructions=instructions)

for name in dir(fc):
    attr = getattr(fc, name)
    if callable(attr) and not name.startswith("__"):
        mcp.add_tool(attr)
