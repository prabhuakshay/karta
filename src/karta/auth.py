"""HTTP Basic Auth helpers for karta."""

import base64
import hmac
import logging


logger = logging.getLogger(__name__)


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
    except Exception:
        logger.debug("Failed to decode Basic Auth credentials")
        return False

    if ":" not in decoded:
        return False

    username, password = decoded.split(":", maxsplit=1)

    username_match = hmac.compare_digest(username, expected_username)
    password_match = hmac.compare_digest(password, expected_password)

    return username_match and password_match
