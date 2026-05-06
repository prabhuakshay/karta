"""Tests for the ``neev share`` subcommand."""

from unittest.mock import patch

import pytest

from neev.cli import main
from neev.cli_share import _base_url, _url_path_for, is_share_invocation
from neev.share import generate_secret, verify


SECRET = generate_secret()


def _write_share_toml(directory, secret_hex=None):
    """Drop a neev.toml with share-secret into the served directory."""
    secret_hex = secret_hex or SECRET.hex()
    (directory / "neev.toml").write_text(f'share-secret = "{secret_hex}"\n')


def test_is_share_invocation_detects_subcommand() -> None:
    assert is_share_invocation(["neev", "share", "foo"]) is True
    assert is_share_invocation(["neev", "share"]) is True
    assert is_share_invocation(["neev"]) is False
    assert is_share_invocation(["neev", "serve"]) is False


def test_base_url_prefers_public_url() -> None:
    assert _base_url("127.0.0.1", 8000, "https://example.com") == "https://example.com"


def test_base_url_rewrites_unspecified_bind() -> None:
    assert _base_url("0.0.0.0", 9000, None) == "http://127.0.0.1:9000"


def test_url_path_for_file(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    assert _url_path_for(tmp_path / "a.txt", tmp_path) == "/a.txt"


def test_url_path_for_nested_file(tmp_path):
    sub = tmp_path / "d"
    sub.mkdir()
    (sub / "b.txt").write_text("x")
    assert _url_path_for(sub / "b.txt", tmp_path) == "/d/b.txt"


def test_url_path_for_directory_root(tmp_path):
    assert _url_path_for(tmp_path, tmp_path) == "/"


def test_url_path_for_missing_exits(tmp_path):
    with pytest.raises(SystemExit):
        _url_path_for(tmp_path / "nope", tmp_path)


def test_url_path_for_escapes_served_exits(tmp_path):
    outside = tmp_path.parent
    with pytest.raises(SystemExit):
        _url_path_for(outside, tmp_path)


def test_share_subcommand_prints_valid_url(tmp_path, capsys):
    _write_share_toml(tmp_path)
    (tmp_path / "v1.zip").write_bytes(b"DATA")
    with patch(
        "sys.argv",
        ["neev", "share", str(tmp_path / "v1.zip"), "-d", str(tmp_path), "--expires", "60"],
    ):
        main()
    out = capsys.readouterr().out.strip()
    assert "/v1.zip?share=" in out


def test_share_subcommand_signed_url_validates(tmp_path, capsys):
    _write_share_toml(tmp_path)
    (tmp_path / "doc.pdf").write_bytes(b"PDF")
    with patch(
        "sys.argv",
        ["neev", "share", str(tmp_path / "doc.pdf"), "-d", str(tmp_path), "--expires", "30"],
    ):
        main()
    captured = capsys.readouterr()
    token = captured.out.strip().split("?share=", 1)[1]
    payload = verify(token, SECRET)
    assert payload is not None
    assert payload.path == "/doc.pdf"
    assert payload.write_allowed is False
    assert payload.file_scope is True


def test_share_subcommand_folder_target_is_folder_scoped(tmp_path, capsys):
    _write_share_toml(tmp_path)
    (tmp_path / "dir").mkdir()
    with patch(
        "sys.argv",
        ["neev", "share", str(tmp_path / "dir"), "-d", str(tmp_path), "--expires", "60"],
    ):
        main()
    captured = capsys.readouterr()
    token = captured.out.strip().split("?share=", 1)[1]
    payload = verify(token, SECRET)
    assert payload is not None
    assert payload.file_scope is False


def test_share_subcommand_write_flag(tmp_path, capsys):
    _write_share_toml(tmp_path)
    (tmp_path / "up").mkdir()
    with patch(
        "sys.argv",
        ["neev", "share", str(tmp_path / "up"), "-d", str(tmp_path), "--expires", "60", "--write"],
    ):
        main()
    captured = capsys.readouterr()
    token = captured.out.strip().split("?share=", 1)[1]
    payload = verify(token, SECRET)
    assert payload is not None
    assert payload.write_allowed is True


def test_share_subcommand_rejects_negative_expires(tmp_path):
    _write_share_toml(tmp_path)
    (tmp_path / "a.txt").write_text("x")
    with (
        patch(
            "sys.argv",
            ["neev", "share", str(tmp_path / "a.txt"), "-d", str(tmp_path), "--expires", "0"],
        ),
        pytest.raises(SystemExit),
    ):
        main()


def test_share_subcommand_rejects_missing_path(tmp_path):
    _write_share_toml(tmp_path)
    with (
        patch(
            "sys.argv",
            ["neev", "share", str(tmp_path / "nope"), "-d", str(tmp_path)],
        ),
        pytest.raises(SystemExit),
    ):
        main()


def test_share_subcommand_errors_when_no_secret_configured(tmp_path, capsys):
    (tmp_path / "a.txt").write_text("x")
    with (
        patch(
            "sys.argv",
            ["neev", "share", str(tmp_path / "a.txt"), "-d", str(tmp_path)],
        ),
        pytest.raises(SystemExit),
    ):
        main()
    err = capsys.readouterr().err
    assert "share-secret is not configured" in err
