"""Token authentication: the FirecREST token, read from a file on every request."""

import time

import jwt

from firecrest_mcp import settings


class TokenAuth:
    def _is_unexpired_jwt(self, token: str) -> bool:
        try:
            # Only the expiry is read here. FirecREST verifies the signature, and the
            # client has no key.
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
        path = settings.token_file
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
        if not self._is_unexpired_jwt(token):
            raise RuntimeError(
                f"Token file {path} holds a token that is invalid or has expired. "
                "Write a new token to it."
            )
        return token
