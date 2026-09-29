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
        token = os.getenv("FIRECREST_TOKEN", None)
        if not token:
            raise RuntimeError("Environment variable FIRECREST_TOKEN is not defined.")
        if not self._is_token_valid(token):
            raise RuntimeError("Token is invalid or has expired.")
        return token


class FirecrestClientWrapper(
    FirecrestComputeToolsMixin,
    FirecrestFilesystemToolsMixin,
    FirecrestStatusToolsMixin,
):
    def __init__(self):
        self.client = Firecrest(
            firecrest_url=os.getenv("FIRECREST_URL", "http://localhost"),
            authorization=TokenAuth(),
        )


fc = FirecrestClientWrapper()
CONTEXT_DIR = Path(__file__).parent / "context"
instructions = None
url = os.getenv("FIRECREST_URL", "http://localhost")
if "roihu" in url:
    instructions = (CONTEXT_DIR / "roihu.md").read_text()
elif "lumi" in url:
    instructions = (CONTEXT_DIR / "lumi.md").read_text()

mcp = FastMCP("FirecREST v2", instructions=instructions)

for name in dir(fc):
    attr = getattr(fc, name)
    if callable(attr) and not name.startswith("__"):
        mcp.add_tool(attr)
