"""Read and merge neev.toml configuration.

Loads ``neev.toml`` from two locations — the served directory (local)
and a user-level config dir — and merges values into CLI arguments.
Precedence: CLI flags > local ``neev.toml`` > user ``neev.toml``.
"""

import argparse
import logging
import os
import tomllib
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


TOML_FILENAME = "neev.toml"

# Keys that neev.toml must never override (security-sensitive).
_DENIED_KEYS = {"directory"}

# Maps toml key names to argparse dest names (only where they differ).
_KEY_MAP = {
    "show-hidden": "show_hidden",
    "enable-zip-download": "enable_zip_download",
    "max-zip-size": "max_zip_size",
    "enable-upload": "enable_upload",
    "read-only": "read_only",
    "public-url": "public_url",
}


def user_config_path() -> Path:
    r"""Resolve the per-user ``neev.toml`` location across platforms.

    Resolution order:

    1. ``$XDG_CONFIG_HOME/neev/neev.toml`` when ``XDG_CONFIG_HOME`` is set
    2. ``%APPDATA%\neev\neev.toml`` on Windows (``os.name == 'nt'``)
    3. ``~/.config/neev/neev.toml`` otherwise (Linux, macOS, BSD)

    Returns:
        The candidate path. The file may or may not exist.
    """
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "neev" / TOML_FILENAME
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "neev" / TOML_FILENAME
    return Path.home() / ".config" / "neev" / TOML_FILENAME


def _read_toml(path: Path) -> dict[str, Any]:
    """Read and parse a TOML file, returning ``{}`` on any failure.

    A missing file is silently ignored. Parse and IO errors log a warning
    but don't raise — config files must never crash startup.

    Args:
        path: Absolute path to a TOML file.

    Returns:
        Parsed TOML as a dict, or empty dict on any error/missing file.
    """
    if not path.is_file():
        return {}
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError) as exc:
        logger.warning("failed to read %s: %s", path, exc)
        return {}
    logger.info("loaded config from %s", path)
    return data


def load_toml(directory: Path) -> dict[str, Any]:
    """Load ``neev.toml`` from the served directory.

    Args:
        directory: The directory to search for ``neev.toml``.

    Returns:
        A dictionary of config values, or empty dict if no file found.
    """
    return _read_toml(directory / TOML_FILENAME)


def load_user_toml() -> dict[str, Any]:
    """Load the per-user ``neev.toml`` from the platform config dir.

    Returns:
        A dictionary of config values, or empty dict if no file found.
    """
    return _read_toml(user_config_path())


def merge_toml_into_args(args: argparse.Namespace, toml_data: dict[str, Any]) -> None:
    """Apply toml values to argparse namespace where nothing more specific is set.

    A toml value is only applied if the corresponding attribute is
    ``None`` — i.e. the user did not pass that flag and no higher-precedence
    source has already filled it. Callers must invoke this in precedence
    order (most specific first) so that local toml overrides user toml.

    Args:
        args: The parsed CLI arguments (modified in place).
        toml_data: The dictionary loaded from a ``neev.toml``.
    """
    for toml_key, value in toml_data.items():
        attr = _KEY_MAP.get(toml_key) or toml_key
        if attr in _DENIED_KEYS:
            logger.warning("ignoring denied config key in neev.toml: %s", toml_key)
            continue
        if not hasattr(args, attr):
            logger.warning("unknown config key in neev.toml: %s", toml_key)
            continue
        if getattr(args, attr) is None:
            setattr(args, attr, value)
