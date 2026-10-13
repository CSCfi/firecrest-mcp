"""Token authentication: the FirecREST token, read from a file on every request."""

import os
import time
from pathlib import Path

import jwt

# Used when FIRECREST_TOKEN_PATH is not set.
DEFAULT_TOKEN_PATH = "~/.firecrest-token"


def token_path() -> Path:
    return Path(os.getenv("FIRECREST_TOKEN_PATH", DEFAULT_TOKEN_PATH)).expanduser()


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
        except (jwt.PyJWTError, KeyError, TypeError):
            return False

    def get_access_token(self):
        path = token_path()
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
