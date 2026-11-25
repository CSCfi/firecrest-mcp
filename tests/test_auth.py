"""Tests for reading and checking the FirecREST token file."""

import time

import jwt
import pytest

from firecrest_mcp import settings
from firecrest_mcp.auth import TokenAuth

# Long enough that PyJWT doesn't warn about the HMAC key length.
KEY = "k" * 32


def make_token(**claims) -> str:
    return jwt.encode(claims, KEY, algorithm="HS256")


VALID = make_token(exp=time.time() + 3600)


@pytest.fixture
def token_file(tmp_path, monkeypatch):
    """Return a function that writes the token file that --token-file names."""
    path = tmp_path / "token"
    monkeypatch.setattr(settings, "token_file", path)

    def write(content: str, mode: int = 0o600):
        path.write_text(content)
        path.chmod(mode)

    return write


def test_valid_token(token_file):
    """A valid token is returned without surrounding whitespace."""
    token_file(f"\n{VALID}\n")
    assert TokenAuth().get_access_token() == VALID


def test_token_reread_on_every_request(token_file):
    """A rewritten token file is used from the next request on."""
    auth = TokenAuth()
    token_file(VALID)
    assert auth.get_access_token() == VALID
    # A different exp gives a different token.
    second_token = make_token(exp=time.time() + 7200)
    token_file(second_token)
    assert auth.get_access_token() == second_token


@pytest.mark.parametrize("mode", [0o640, 0o604, 0o620, 0o602, 0o610, 0o601])
def test_file_accessible_by_others_refused(token_file, mode):
    """Any permission bit for group or others makes the file unusable."""
    token_file(VALID, mode)
    with pytest.raises(RuntimeError, match="accessible by other users"):
        TokenAuth().get_access_token()


def test_missing_file(token_file):
    with pytest.raises(RuntimeError, match="Could not read token file"):
        TokenAuth().get_access_token()


def test_empty_file(token_file):
    token_file(" \n")
    with pytest.raises(RuntimeError, match="is empty"):
        TokenAuth().get_access_token()


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(make_token(exp=time.time() - 60), id="expired"),
        pytest.param(make_token(sub="me"), id="no-exp"),
        pytest.param(make_token(exp="tomorrow"), id="bad-exp"),
        pytest.param("not-a-jwt", id="not-a-jwt"),
    ],
)
def test_invalid_token_refused(token_file, token):
    token_file(token)
    with pytest.raises(RuntimeError, match="invalid or has expired"):
        TokenAuth().get_access_token()


def test_signature_not_verified(token_file):
    """The signature can't be checked without FirecREST's key, so a token signed
    with any key is accepted; FirecREST itself verifies it."""
    token = jwt.encode({"exp": time.time() + 3600}, "x" * 32, algorithm="HS256")
    token_file(token)
    assert TokenAuth().get_access_token() == token
