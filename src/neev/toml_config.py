"""Read and merge neev.toml configuration.

Loads ``neev.toml`` from the served directory and merges its values
with CLI arguments, where CLI flags take precedence.
"""

import argparse
import logging
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


def load_toml(directory: Path) -> dict[str, Any]:
    """Load neev.toml from the given directory.

    Args:
        directory: The directory to search for ``neev.toml``.

    Returns:
        A dictionary of config values, or empty dict if no file found.
    """
    toml_path = directory / TOML_FILENAME
    if not toml_path.is_file():
        return {}
    try:
        with toml_path.open("rb") as f:
            data = tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError) as exc:
        logger.warning("failed to read %s: %s", toml_path, exc)
        return {}
    logger.info("loaded config from %s", toml_path)
    return data


def merge_toml_into_args(args: argparse.Namespace, toml_data: dict[str, Any]) -> None:
    """Apply toml values to argparse namespace where CLI didn't override.

    CLI arguments take precedence. A toml value is only applied if the
    corresponding attribute is ``None`` (i.e. the user did not pass that
    flag). This relies on the CLI parser using ``None`` as the default
    sentinel for every optional flag; real defaults are applied later by
    :func:`neev.cli.build_config`.

    Args:
        args: The parsed CLI arguments (modified in place).
        toml_data: The dictionary loaded from ``neev.toml``.
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
