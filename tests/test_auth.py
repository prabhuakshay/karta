"""Unit tests for neev.auth — credential validation, session store, cookies."""

import base64
from unittest.mock import patch

from neev.auth import (
    TOKEN_TTL,
    SessionStore,
    check_basic_auth,
    check_credentials,
    parse_cookie,
)


# -- Unit tests: check_basic_auth --------------------------------------------


def _encode_creds(username: str, password: str) -> str:
    """Build a valid Basic Auth header value."""
    raw = f"{username}:{password}".encode()
    return f"Basic {base64.b64encode(raw).decode()}"


class TestCheckBasicAuth:
    def test_valid_credentials(self):
        header = _encode_creds("alice", "secret")
        assert check_basic_auth(header, "alice", "secret") is True

    def test_wrong_username(self):
        header = _encode_creds("bob", "secret")
        assert check_basic_auth(header, "alice", "secret") is False

    def test_wrong_password(self):
        header = _encode_creds("alice", "wrong")
        assert check_basic_auth(header, "alice", "secret") is False

    def test_none_header(self):
        assert check_basic_auth(None, "alice", "secret") is False

    def test_empty_header(self):
        assert check_basic_auth("", "alice", "secret") is False

    def test_missing_basic_prefix(self):
        assert check_basic_auth("Bearer token", "alice", "secret") is False

    def test_malformed_base64(self):
        assert check_basic_auth("Basic !!!bad!!!", "alice", "secret") is False

    def test_no_colon_in_decoded(self):
        encoded = base64.b64encode(b"nocolon").decode()
        assert check_basic_auth(f"Basic {encoded}", "alice", "secret") is False

    def test_password_with_colon(self):
        header = _encode_creds("alice", "pass:word:extra")
        assert check_basic_auth(header, "alice", "pass:word:extra") is True

    def test_unicode_credentials(self):
        header = _encode_creds("ålice", "sëcret")
        assert check_basic_auth(header, "ålice", "sëcret") is True


# -- Unit tests: check_credentials ------------------------------------------


class TestCheckCredentials:
    def test_valid(self):
        assert check_credentials("alice", "secret", "alice", "secret") is True

    def test_wrong_password(self):
        assert check_credentials("alice", "wrong", "alice", "secret") is False

    def test_unicode(self):
        assert check_credentials("ålice", "sëcret", "ålice", "sëcret") is True


# -- Unit tests: SessionStore ------------------------------------------------


class TestSessionStore:
    def test_create_and_validate(self):
        store = SessionStore()
        token = store.create()
        assert store.validate(token) is True

    def test_invalid_token(self):
        store = SessionStore()
        assert store.validate("nonexistent") is False

    def test_invalidate(self):
        store = SessionStore()
        token = store.create()
        store.invalidate(token)
        assert store.validate(token) is False

    def test_invalidate_unknown_token(self):
        store = SessionStore()
        store.invalidate("nonexistent")

    def test_expired_token_rejected(self):
        store = SessionStore()
        with patch("neev.auth.time") as mock_time:
            mock_time.monotonic.return_value = 0.0
            token = store.create()
            mock_time.monotonic.return_value = TOKEN_TTL + 1
            assert store.validate(token) is False

    def test_unexpired_token_accepted(self):
        store = SessionStore()
        with patch("neev.auth.time") as mock_time:
            mock_time.monotonic.return_value = 0.0
            token = store.create()
            mock_time.monotonic.return_value = TOKEN_TTL - 1
            assert store.validate(token) is True

    def test_create_prunes_expired_tokens(self):
        store = SessionStore()
        with patch("neev.auth.time") as mock_time:
            mock_time.monotonic.return_value = 0.0
            old_token = store.create()
            mock_time.monotonic.return_value = TOKEN_TTL + 1
            store.create()  # triggers prune
            assert old_token not in store._tokens


# -- Unit tests: parse_cookie ------------------------------------------------


class TestParseCookie:
    def test_single_cookie(self):
        assert parse_cookie("neev_session=abc123", "neev_session") == "abc123"

    def test_multiple_cookies(self):
        header = "foo=bar; neev_session=abc123; baz=qux"
        assert parse_cookie(header, "neev_session") == "abc123"

    def test_missing_cookie(self):
        assert parse_cookie("foo=bar", "neev_session") is None

    def test_none_header(self):
        assert parse_cookie(None, "neev_session") is None

    def test_empty_header(self):
        assert parse_cookie("", "neev_session") is None

    def test_no_equals(self):
        assert parse_cookie("malformed", "neev_session") is None
