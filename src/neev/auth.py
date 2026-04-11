"""Authentication and session management for neev."""

import base64
import hmac
import logging
import secrets
import threading
import time


logger = logging.getLogger(__name__)

# Sessions older than this are considered expired and will be pruned.
TOKEN_TTL = 86400  # 24 hours in seconds

COOKIE_NAME = "neev_session"


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
    """In-memory session token store with TTL-based expiry.

    Each token is stored alongside its creation timestamp. Expired tokens are
    pruned on every ``create()`` call. ``validate()`` also rejects tokens that
    have exceeded ``TOKEN_TTL`` without waiting for the next prune sweep.

    Tokens are generated with ``secrets.token_urlsafe()`` for cryptographic
    randomness.
    """

    def __init__(self) -> None:
        """Initialize an empty session store."""
        self._lock = threading.Lock()
        # Maps token → monotonic creation timestamp.
        self._tokens: dict[str, float] = {}

    def create(self) -> str:
        """Create a new session token, pruning expired tokens first.

        Returns:
            A cryptographically random URL-safe token.
        """
        with self._lock:
            self._prune()
            token = secrets.token_urlsafe(32)
            self._tokens[token] = time.monotonic()
            return token

    def validate(self, token: str) -> bool:
        """Check whether a session token is valid and unexpired.

        Args:
            token: The token to validate.

        Returns:
            ``True`` if the token exists and has not exceeded ``TOKEN_TTL``.
        """
        with self._lock:
            created_at = self._tokens.get(token)
            if created_at is None:
                return False
            return (time.monotonic() - created_at) < TOKEN_TTL

    def invalidate(self, token: str) -> None:
        """Remove a session token.

        Args:
            token: The token to invalidate.
        """
        with self._lock:
            self._tokens.pop(token, None)

    def _prune(self) -> None:
        """Remove all tokens that have exceeded ``TOKEN_TTL``."""
        now = time.monotonic()
        expired = [t for t, ts in self._tokens.items() if (now - ts) >= TOKEN_TTL]
        for token in expired:
            del self._tokens[token]
        if expired:
            logger.debug("Pruned %d expired session token(s)", len(expired))


# -- Login rate limiting -----------------------------------------------------

# After this many consecutive failures, start blocking.
MAX_LOGIN_ATTEMPTS = 5

# Initial cooldown in seconds; doubles on each subsequent failure.
BASE_COOLDOWN = 30

# Never block longer than this.
MAX_COOLDOWN = 300


class LoginRateLimiter:
    """Per-IP login rate limiter with exponential backoff.

    Tracks consecutive failed login attempts per client IP. After
    ``MAX_LOGIN_ATTEMPTS`` failures, further attempts are blocked for a
    cooldown that doubles with each additional failure, up to
    ``MAX_COOLDOWN`` seconds.

    Thread-safe — uses the same locking pattern as ``SessionStore``.
    """

    def __init__(self) -> None:
        """Initialize an empty rate limiter."""
        self._lock = threading.Lock()
        # Maps IP → (consecutive_failures, last_failure_monotonic).
        self._attempts: dict[str, tuple[int, float]] = {}

    def is_blocked(self, ip: str) -> bool:
        """Check whether an IP is currently in a cooldown period.

        Args:
            ip: The client IP address.

        Returns:
            ``True`` if the IP must wait before retrying.
        """
        with self._lock:
            record = self._attempts.get(ip)
            if record is None:
                return False
            failures, last_failure = record
            if failures < MAX_LOGIN_ATTEMPTS:
                return False
            cooldown = min(
                BASE_COOLDOWN * 2 ** (failures - MAX_LOGIN_ATTEMPTS),
                MAX_COOLDOWN,
            )
            return (time.monotonic() - last_failure) < cooldown

    def record_failure(self, ip: str) -> None:
        """Record a failed login attempt for an IP.

        Args:
            ip: The client IP address.
        """
        with self._lock:
            record = self._attempts.get(ip)
            failures = (record[0] + 1) if record else 1
            self._attempts[ip] = (failures, time.monotonic())
        logger.warning("Failed login attempt %d from %s", failures, ip)

    def record_success(self, ip: str) -> None:
        """Clear the failure record for an IP after a successful login.

        Args:
            ip: The client IP address.
        """
        with self._lock:
            self._attempts.pop(ip, None)


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
