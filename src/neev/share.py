"""Signed share tokens for scoped, time-limited URL access.

Tokens are generated and verified entirely from a server-side secret; neev
does not persist anything per-token. A token carries a normalized path
prefix, an expiry (epoch seconds), and a write flag. The server checks the
HMAC, checks expiry, then checks the request path against the prefix.

Wire format::

    <base64url(payload_json)>.<base64url(hmac_sha256(payload_bytes))>

The payload is JSON ``{"p": "/releases/v1.zip", "e": 1713000000, "w": false}``.
Both segments use base64url without padding.
"""

import base64
import binascii
import hmac
import json
import logging
import secrets
import time
from dataclasses import dataclass
from hashlib import sha256


logger = logging.getLogger(__name__)


# Share secrets are 32 random bytes. Smaller is a footgun; larger buys
# nothing meaningful against HMAC-SHA256.
_SECRET_BYTES = 32


@dataclass(frozen=True)
class SharePayload:
    """Decoded, verified share-token payload.

    Attributes:
        path: Normalized URL path the token scopes access to. Always starts
            with ``/``. May refer to a file or a directory prefix.
        expires_at: Expiry as a Unix epoch timestamp (seconds).
        write_allowed: Whether the token grants POST/upload permission.
    """

    path: str
    expires_at: int
    write_allowed: bool


def generate_secret() -> bytes:
    """Return a fresh random share secret suitable for HMAC-SHA256."""
    return secrets.token_bytes(_SECRET_BYTES)


def parse_secret_hex(value: str) -> bytes:
    """Decode a hex string into a secret, rejecting obviously-bad values.

    Args:
        value: Hex-encoded secret from config (any length ≥ 32 bytes decoded).

    Returns:
        The decoded secret bytes.

    Raises:
        ValueError: If the string is not valid hex or decodes to too few bytes.
    """
    try:
        raw = bytes.fromhex(value.strip())
    except ValueError as exc:
        msg = f"share-secret is not valid hex: {exc}"
        raise ValueError(msg) from None
    if len(raw) < _SECRET_BYTES:
        msg = f"share-secret must decode to at least {_SECRET_BYTES} bytes, got {len(raw)}"
        raise ValueError(msg)
    return raw


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _normalize_path(path: str) -> str:
    """Normalize a path so signed prefixes compare cleanly.

    Leading slash is enforced; trailing slash (except at root) is stripped so
    ``/releases`` and ``/releases/`` sign identically.
    """
    if not path.startswith("/"):
        path = "/" + path
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return path


def sign(path: str, expires_at: int, write_allowed: bool, secret: bytes) -> str:
    """Create a signed share token for the given scope.

    Args:
        path: URL path to scope the token to (file or directory prefix).
        expires_at: Expiry as Unix epoch seconds.
        write_allowed: Whether POSTs are permitted under this token.
        secret: The server's share secret.

    Returns:
        The ``payload.hmac`` token string.
    """
    payload = {"p": _normalize_path(path), "e": int(expires_at), "w": bool(write_allowed)}
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    mac = hmac.new(secret, payload_bytes, sha256).digest()
    return f"{_b64url_encode(payload_bytes)}.{_b64url_encode(mac)}"


def verify(token: str, secret: bytes, now: int | None = None) -> SharePayload | None:  # noqa: PLR0911 -- defensive early-return parser for untrusted input
    """Verify a share token and return its payload on success.

    Performs, in order: shape check, base64 decode, constant-time HMAC
    comparison, payload JSON parse, expiry check. Any failure returns
    ``None`` — callers should treat this as "no share auth" and fall back to
    normal auth.

    Args:
        token: The raw ``payload.hmac`` string from the query parameter.
        secret: The server's share secret.
        now: Current time as epoch seconds; defaults to ``time.time()``.

    Returns:
        The decoded ``SharePayload`` if the token is valid and unexpired,
        otherwise ``None``.
    """
    if not token or "." not in token:
        return None
    payload_b64, mac_b64 = token.rsplit(".", maxsplit=1)
    if not payload_b64 or not mac_b64:
        return None

    try:
        payload_bytes = _b64url_decode(payload_b64)
        provided_mac = _b64url_decode(mac_b64)
    except (ValueError, binascii.Error):
        return None

    expected_mac = hmac.new(secret, payload_bytes, sha256).digest()
    if not hmac.compare_digest(provided_mac, expected_mac):
        return None

    try:
        data = json.loads(payload_bytes.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None

    if not isinstance(data, dict):
        return None
    path = data.get("p")
    expires_at = data.get("e")
    write_allowed = data.get("w", False)
    if not isinstance(path, str) or not isinstance(expires_at, int) or isinstance(expires_at, bool):
        return None
    if not isinstance(write_allowed, bool):
        return None

    current = int(time.time()) if now is None else now
    if current >= expires_at:
        return None

    return SharePayload(
        path=_normalize_path(path),
        expires_at=expires_at,
        write_allowed=write_allowed,
    )


def path_in_scope(request_path: str, scope: str) -> bool:
    """Check whether a request path is covered by a token's scope.

    Uses exact match or ``scope + "/"`` prefix match so ``/releases`` does
    not accidentally grant access to ``/releases-private``.

    Args:
        request_path: The path from the incoming request (URL-decoded).
        scope: The ``p`` field from a verified payload.

    Returns:
        ``True`` if the request is within scope.
    """
    normalized = _normalize_path(request_path)
    if scope == "/":
        return True
    return normalized == scope or normalized.startswith(scope + "/")


def build_share_url(base_url: str, path: str, token: str) -> str:
    """Assemble a public share URL from a base, path, and token.

    Args:
        base_url: Public base URL without trailing slash (e.g. ``https://x.example``).
        path: The scoped path (leading slash enforced by sign()).
        token: The output of :func:`sign`.

    Returns:
        A full URL with the token in the ``share`` query parameter.
    """
    normalized = _normalize_path(path)
    return f"{base_url.rstrip('/')}{normalized}?share={token}"
