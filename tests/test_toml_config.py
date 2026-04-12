"""Tests for neev.toml configuration loading and merging."""

import argparse

import pytest

from neev.toml_config import load_toml, merge_toml_into_args


@pytest.fixture
def toml_dir(tmp_path):
    """Create a temp directory with a neev.toml file."""
    toml_content = """\
host = "0.0.0.0"
port = 9000
banner = "Test banner"
show-hidden = true
enable-upload = true
enable-zip-download = true
max-zip-size = 200
"""
    (tmp_path / "neev.toml").write_text(toml_content)
    return tmp_path


@pytest.fixture
def parser():
    """Create a minimal argparse parser matching neev's CLI."""
    p = argparse.ArgumentParser()
    p.add_argument("directory", nargs="?", default=".")
    p.add_argument("--host", default=None)
    p.add_argument("--port", "-p", default=None, type=int)
    p.add_argument("--auth", default=None)
    p.add_argument("--show-hidden", action=argparse.BooleanOptionalAction, default=None)
    p.add_argument("--enable-zip-download", action=argparse.BooleanOptionalAction, default=None)
    p.add_argument("--max-zip-size", default=None, type=int)
    p.add_argument("--enable-upload", action=argparse.BooleanOptionalAction, default=None)
    p.add_argument("--read-only", action=argparse.BooleanOptionalAction, default=None)
    p.add_argument("--banner", default=None)
    return p


class TestLoadToml:
    def test_load_existing_toml(self, toml_dir):
        data = load_toml(toml_dir)
        assert data["host"] == "0.0.0.0"
        assert data["port"] == 9000
        assert data["banner"] == "Test banner"

    def test_load_missing_toml(self, tmp_path):
        data = load_toml(tmp_path)
        assert data == {}

    def test_load_invalid_toml(self, tmp_path):
        (tmp_path / "neev.toml").write_text("invalid [[[ toml content")
        data = load_toml(tmp_path)
        assert data == {}


class TestMergeToml:
    def test_toml_values_applied_as_defaults(self, toml_dir, parser):
        args = parser.parse_args([])
        data = load_toml(toml_dir)
        merge_toml_into_args(args, data)
        assert args.host == "0.0.0.0"
        assert args.port == 9000
        assert args.banner == "Test banner"
        assert args.show_hidden is True
        assert args.enable_upload is True

    def test_cli_overrides_toml(self, toml_dir, parser):
        args = parser.parse_args(["--host", "192.168.1.1", "--port", "4000"])
        data = load_toml(toml_dir)
        merge_toml_into_args(args, data)
        assert args.host == "192.168.1.1"
        assert args.port == 4000
        # Non-overridden values from toml
        assert args.banner == "Test banner"

    def test_unknown_key_ignored(self, tmp_path, parser):
        (tmp_path / "neev.toml").write_text('unknown-key = "value"\n')
        args = parser.parse_args([])
        data = load_toml(tmp_path)
        merge_toml_into_args(args, data)
        assert not hasattr(args, "unknown_key")

    def test_empty_toml_no_changes(self, parser):
        args = parser.parse_args([])
        merge_toml_into_args(args, {})
        assert args.host is None
        assert args.port is None

    def test_denied_directory_key_ignored(self, parser, caplog):
        """Setting `directory` via neev.toml must be ignored (security)."""
        args = parser.parse_args([])
        original = args.directory
        merge_toml_into_args(args, {"directory": "/etc"})
        assert args.directory == original
        assert any("denied" in r.message.lower() for r in caplog.records)

    def test_cli_value_matching_default_still_wins(self, toml_dir, parser):
        """Regression for #105: --port 8000 (matches real default) must beat TOML port = 9000.

        Before the fix, merge compared ``current == parser_default``; since the
        parser default was 8000, an explicit ``--port 8000`` looked unset and
        TOML (9000) overrode it. With None sentinels, this is unambiguous.
        """
        args = parser.parse_args(["--port", "8000"])
        data = load_toml(toml_dir)
        merge_toml_into_args(args, data)
        assert args.port == 8000
