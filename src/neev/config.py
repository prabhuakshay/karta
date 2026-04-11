"""Configuration dataclass for neev."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    """Immutable configuration resolved from CLI arguments and environment.

    All settings are finalized at parse time. For example, ``--read-only``
    forces ``enable_upload`` to ``False`` before this object is created, so
    consumers never need to check a separate read-only flag.

    ``__post_init__`` normalizes ``directory`` to its real path (resolving
    symlinks) and pre-computes ``auth_enabled`` so these are done once at
    startup, not per-request.

    Attributes:
        directory: Absolute, realpath-resolved path to the served directory.
        host: Network address to bind the server to.
        port: TCP port to listen on.
        username: HTTP Basic Auth username, or ``None`` if auth is disabled.
        password: HTTP Basic Auth password, or ``None`` if auth is disabled.
        show_hidden: Whether dotfiles and dotdirs appear in listings.
        enable_zip_download: Whether on-the-fly ZIP downloads of folders are allowed.
        max_zip_size: Maximum size in bytes for generated ZIP archives.
        enable_upload: Whether file uploads are accepted.
        auth_enabled: Whether HTTP Basic Auth is active (computed at init).
    """

    directory: Path
    host: str
    port: int
    username: str | None
    password: str | None
    show_hidden: bool
    enable_zip_download: bool
    max_zip_size: int
    enable_upload: bool
    banner: str | None = None
    auth_enabled: bool = False

    def __post_init__(self) -> None:
        """Resolve directory realpath and compute auth_enabled once."""
        object.__setattr__(self, "directory", Path(os.path.realpath(self.directory)))
        object.__setattr__(
            self,
            "auth_enabled",
            self.username is not None and self.password is not None,
        )
