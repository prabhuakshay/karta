"""Authentication and session management for karta."""

import base64
import hmac
import logging
import secrets


logger = logging.getLogger(__name__)

COOKIE_NAME = "karta_session"


# -- Credential validation ---------------------------------------------------


def check_basic_auth(
    authorization_header: str | None,
    expected_username: str,
    expected_password: str,
) -> bool:
    """Validate a Basic Auth Authorization header against expected credentials.

    Uses ``hmac.compare_digest()`` for constant-time comparison to prevent
    timing attacks.

    Args:
        authorization_header: The raw ``Authorization`` header value, or
            ``None`` if the header was not sent.
        expected_username: The username to match against.
        expected_password: The password to match against.

    Returns:
        ``True`` if credentials match, ``False`` otherwise.
    """
    if not authorization_header:
        return False

    if not authorization_header.startswith("Basic "):
        return False

    encoded = authorization_header[len("Basic ") :]

    try:
        decoded = base64.b64decode(encoded).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        logger.debug("Failed to decode Basic Auth credentials")
        return False

    if ":" not in decoded:
        return False

    username, password = decoded.split(":", maxsplit=1)

    # Compare as bytes — hmac.compare_digest() rejects non-ASCII str
    username_match = hmac.compare_digest(
        username.encode("utf-8"), expected_username.encode("utf-8")
    )
    password_match = hmac.compare_digest(
        password.encode("utf-8"), expected_password.encode("utf-8")
    )

    return username_match and password_match


def check_credentials(
    username: str,
    password: str,
    expected_username: str,
    expected_password: str,
) -> bool:
    """Validate plaintext credentials against expected values.

    Uses ``hmac.compare_digest()`` for constant-time comparison.

    Args:
        username: The submitted username.
        password: The submitted password.
        expected_username: The username to match against.
        expected_password: The password to match against.

    Returns:
        ``True`` if both match, ``False`` otherwise.
    """
    username_match = hmac.compare_digest(
        username.encode("utf-8"), expected_username.encode("utf-8")
    )
    password_match = hmac.compare_digest(
        password.encode("utf-8"), expected_password.encode("utf-8")
    )
    return username_match and password_match


# -- Session management ------------------------------------------------------


class SessionStore:
    """In-memory session token store.

    Sessions persist until the server process exits. Tokens are generated
    with ``secrets.token_urlsafe()`` for cryptographic randomness.
    """

    def __init__(self) -> None:
        """Initialize an empty session store."""
        self._tokens: set[str] = set()

    def create(self) -> str:
        """Create a new session token.

        Returns:
            A cryptographically random URL-safe token.
        """
        token = secrets.token_urlsafe(32)
        self._tokens.add(token)
        return token

    def validate(self, token: str) -> bool:
        """Check whether a session token is valid.

        Args:
            token: The token to validate.

        Returns:
            ``True`` if the token exists in the store.
        """
        return token in self._tokens

    def invalidate(self, token: str) -> None:
        """Remove a session token.

        Args:
            token: The token to invalidate.
        """
        self._tokens.discard(token)


# -- Cookie helpers ----------------------------------------------------------


def parse_cookie(cookie_header: str | None, name: str) -> str | None:
    """Extract a named value from a Cookie header.

    Args:
        cookie_header: The raw ``Cookie`` header value, or ``None``.
        name: The cookie name to look for.

    Returns:
        The cookie value, or ``None`` if not found.
    """
    if not cookie_header:
        return None

    for raw_pair in cookie_header.split(";"):
        stripped = raw_pair.strip()
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", maxsplit=1)
        if key.strip() == name:
            return value.strip()

    return None
