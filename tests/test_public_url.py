"""Tests for the --public-url flag, NEEV_PUBLIC_URL env var, and TOML key."""

from unittest.mock import patch

import pytest

from neev.cli import _build_parser, _print_startup_banner, build_config
from neev.toml_config import merge_toml_into_args


# -- Parsing & validation ---------------------------------------------------


class TestPublicUrlParsing:
    def test_valid_https(self, tmp_path):
        parser = _build_parser()
        args = parser.parse_args([str(tmp_path), "--public-url", "https://files.example.com"])
        with patch.dict("os.environ", {}, clear=True):
            config = build_config(args, tmp_path.resolve())
        assert config.public_url == "https://files.example.com"

    def test_valid_http(self, tmp_path):
        parser = _build_parser()
        args = parser.parse_args([str(tmp_path), "--public-url", "http://example.com:8080"])
        with patch.dict("os.environ", {}, clear=True):
            config = build_config(args, tmp_path.resolve())
        assert config.public_url == "http://example.com:8080"

    def test_trailing_slash_stripped(self, tmp_path):
        parser = _build_parser()
        args = parser.parse_args([str(tmp_path), "--public-url", "https://example.com/"])
        with patch.dict("os.environ", {}, clear=True):
            config = build_config(args, tmp_path.resolve())
        assert config.public_url == "https://example.com"

    def test_subpath_trailing_slash_stripped(self, tmp_path):
        parser = _build_parser()
        args = parser.parse_args([str(tmp_path), "--public-url", "https://example.com/files/"])
        with patch.dict("os.environ", {}, clear=True):
            config = build_config(args, tmp_path.resolve())
        assert config.public_url == "https://example.com/files"

    def test_default_none(self, tmp_path):
        parser = _build_parser()
        args = parser.parse_args([str(tmp_path)])
        with patch.dict("os.environ", {}, clear=True):
            config = build_config(args, tmp_path.resolve())
        assert config.public_url is None

    @pytest.mark.parametrize(
        "bad",
        [
            "example.com",
            "ftp://example.com",
            "https://",
            "https://example.com?x=1",
            "https://example.com#frag",
        ],
    )
    def test_invalid_rejected(self, tmp_path, bad):
        parser = _build_parser()
        args = parser.parse_args([str(tmp_path), "--public-url", bad])
        with patch.dict("os.environ", {}, clear=True), pytest.raises(SystemExit):
            build_config(args, tmp_path.resolve())


# -- Precedence -------------------------------------------------------------


class TestPublicUrlPrecedence:
    def test_env_var(self, tmp_path):
        parser = _build_parser()
        args = parser.parse_args([str(tmp_path)])
        with patch.dict("os.environ", {"NEEV_PUBLIC_URL": "https://env.example.com"}):
            config = build_config(args, tmp_path.resolve())
        assert config.public_url == "https://env.example.com"

    def test_cli_overrides_env(self, tmp_path):
        parser = _build_parser()
        args = parser.parse_args([str(tmp_path), "--public-url", "https://cli.example.com"])
        with patch.dict("os.environ", {"NEEV_PUBLIC_URL": "https://env.example.com"}):
            config = build_config(args, tmp_path.resolve())
        assert config.public_url == "https://cli.example.com"

    def test_toml_applied_when_cli_unset(self, tmp_path):
        parser = _build_parser()
        args = parser.parse_args([str(tmp_path)])
        merge_toml_into_args(args, {"public-url": "https://toml.example.com"})
        with patch.dict("os.environ", {}, clear=True):
            config = build_config(args, tmp_path.resolve())
        assert config.public_url == "https://toml.example.com"

    def test_cli_overrides_toml(self, tmp_path):
        parser = _build_parser()
        args = parser.parse_args([str(tmp_path), "--public-url", "https://cli.example.com"])
        merge_toml_into_args(args, {"public-url": "https://toml.example.com"})
        with patch.dict("os.environ", {}, clear=True):
            config = build_config(args, tmp_path.resolve())
        assert config.public_url == "https://cli.example.com"


# -- Banner -----------------------------------------------------------------


class TestBanner:
    def test_public_url_shown_prominently(self, tmp_path, capsys):
        parser = _build_parser()
        args = parser.parse_args([str(tmp_path), "--public-url", "https://files.example.com"])
        with patch.dict("os.environ", {}, clear=True):
            config = build_config(args, tmp_path.resolve())
        _print_startup_banner(config)
        out = capsys.readouterr().out
        assert "https://files.example.com" in out
        assert "bound to http://127.0.0.1:8000" in out

    def test_no_banner_change_when_unset(self, tmp_path, capsys):
        parser = _build_parser()
        args = parser.parse_args([str(tmp_path)])
        with patch.dict("os.environ", {}, clear=True):
            config = build_config(args, tmp_path.resolve())
        _print_startup_banner(config)
        out = capsys.readouterr().out
        assert "http://127.0.0.1:8000" in out
        assert "bound to" not in out
