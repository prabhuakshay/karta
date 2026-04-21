"""Tests for signed share-token primitives."""

import base64
import hmac
import json
import time
from hashlib import sha256

import pytest

from neev.share import (
    SharePayload,
    build_share_url,
    generate_secret,
    parse_secret_hex,
    path_in_scope,
    sign,
    verify,
)


@pytest.fixture
def secret() -> bytes:
    return generate_secret()


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _forge(secret: bytes, raw_payload: bytes) -> str:
    """Sign arbitrary bytes with the secret to bypass our sign() validation."""
    mac = hmac.new(secret, raw_payload, sha256).digest()
    return f"{_b64(raw_payload)}.{_b64(mac)}"


# -- sign/verify happy path ----------------------------------------------------


def test_verify_returns_payload_for_valid_unexpired_token(secret: bytes) -> None:
    expires = int(time.time()) + 60
    token = sign("/releases/v1.zip", expires, write_allowed=False, secret=secret)
    payload = verify(token, secret)
    assert payload == SharePayload(path="/releases/v1.zip", expires_at=expires, write_allowed=False)


def test_verify_preserves_write_flag(secret: bytes) -> None:
    token = sign("/uploads", int(time.time()) + 60, write_allowed=True, secret=secret)
    payload = verify(token, secret)
    assert payload is not None
    assert payload.write_allowed is True


def test_sign_normalizes_trailing_slash(secret: bytes) -> None:
    t1 = sign("/releases/", int(time.time()) + 60, False, secret)
    t2 = sign("/releases", int(time.time()) + 60, False, secret)
    p1 = verify(t1, secret)
    p2 = verify(t2, secret)
    assert p1 is not None
    assert p2 is not None
    assert p1.path == "/releases"
    assert p2.path == "/releases"


def test_sign_adds_leading_slash(secret: bytes) -> None:
    token = sign("releases/v1.zip", int(time.time()) + 60, False, secret)
    payload = verify(token, secret)
    assert payload is not None
    assert payload.path == "/releases/v1.zip"


# -- verify failure modes -----------------------------------------------------


def test_expired_token_returns_none(secret: bytes) -> None:
    token = sign("/x", int(time.time()) - 1, False, secret)
    assert verify(token, secret) is None


def test_tampered_hmac_returns_none(secret: bytes) -> None:
    token = sign("/x", int(time.time()) + 60, False, secret)
    body, mac = token.rsplit(".", 1)
    corrupted = body + "." + ("A" if mac[0] != "A" else "B") + mac[1:]
    assert verify(corrupted, secret) is None


def test_tampered_payload_returns_none(secret: bytes) -> None:
    token = sign("/x", int(time.time()) + 60, False, secret)
    body, mac = token.rsplit(".", 1)
    corrupted = ("A" if body[0] != "A" else "B") + body[1:] + "." + mac
    assert verify(corrupted, secret) is None


def test_wrong_secret_returns_none(secret: bytes) -> None:
    token = sign("/x", int(time.time()) + 60, False, secret)
    assert verify(token, generate_secret()) is None


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "no-dot",
        ".onlymac",
        "onlybody.",
        "!!!not-base64!!!.!!!",
        "abc.def",
    ],
)
def test_malformed_tokens_return_none(secret: bytes, bad: str) -> None:
    assert verify(bad, secret) is None


def test_payload_non_json_bytes_returns_none(secret: bytes) -> None:
    assert verify(_forge(secret, b"\xff\xfe not json"), secret) is None


def test_payload_not_dict_returns_none(secret: bytes) -> None:
    assert verify(_forge(secret, json.dumps([1, 2, 3]).encode()), secret) is None


def test_payload_missing_fields_returns_none(secret: bytes) -> None:
    assert verify(_forge(secret, json.dumps({"p": "/x"}).encode()), secret) is None


def test_payload_boolean_masquerading_as_int_rejected(secret: bytes) -> None:
    raw = json.dumps({"p": "/x", "e": True, "w": False}).encode()
    assert verify(_forge(secret, raw), secret) is None


def test_payload_write_wrong_type_rejected(secret: bytes) -> None:
    raw = json.dumps({"p": "/x", "e": int(time.time()) + 60, "w": "yes"}).encode()
    assert verify(_forge(secret, raw), secret) is None


def test_verify_now_override(secret: bytes) -> None:
    exp = 2_000_000_000
    token = sign("/x", exp, False, secret)
    assert verify(token, secret, now=exp - 1) is not None
    assert verify(token, secret, now=exp) is None
    assert verify(token, secret, now=exp + 1) is None


# -- path scoping -------------------------------------------------------------


@pytest.mark.parametrize(
    ("request_path", "scope", "expected"),
    [
        ("/releases/v1.zip", "/releases/v1.zip", True),
        ("/releases/v1.zip", "/releases", True),
        ("/releases", "/releases", True),
        ("/releases/", "/releases", True),
        ("/releases/sub/file", "/releases", True),
        ("/releases-private", "/releases", False),
        ("/releases-private/x", "/releases", False),
        ("/other", "/releases", False),
        ("/anything", "/", True),
        ("/", "/", True),
    ],
)
def test_path_in_scope(request_path: str, scope: str, expected: bool) -> None:
    assert path_in_scope(request_path, scope) is expected


# -- secret helpers -----------------------------------------------------------


def test_parse_secret_hex_roundtrip() -> None:
    raw = generate_secret()
    assert parse_secret_hex(raw.hex()) == raw


def test_parse_secret_hex_rejects_short() -> None:
    with pytest.raises(ValueError, match="at least"):
        parse_secret_hex("abcd")


def test_parse_secret_hex_rejects_non_hex() -> None:
    with pytest.raises(ValueError, match="not valid hex"):
        parse_secret_hex("nothexstring" * 10)


# -- URL builder --------------------------------------------------------------


def test_build_share_url(secret: bytes) -> None:
    token = sign("/releases/v1.zip", int(time.time()) + 60, False, secret)
    url = build_share_url("https://example.com/", "/releases/v1.zip", token)
    assert url.startswith("https://example.com/releases/v1.zip?share=")
    assert url.count("?share=") == 1


def test_build_share_url_handles_subpath_base(secret: bytes) -> None:
    token = sign("/a", int(time.time()) + 60, False, secret)
    url = build_share_url("https://example.com/neev", "/a", token)
    assert url.startswith("https://example.com/neev/a?share=")
