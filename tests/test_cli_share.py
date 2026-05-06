"""Tests for the ``neev share`` subcommand."""

from unittest.mock import patch

import pytest

from neev.cli import main
from neev.cli_share import _base_url, _url_path_for, is_share_invocation
from neev.share import verify


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
    (tmp_path / "v1.zip").write_bytes(b"DATA")
    with patch(
        "sys.argv",
        ["neev", "share", str(tmp_path / "v1.zip"), "-d", str(tmp_path), "--expires", "60"],
    ):
        main()
    out = capsys.readouterr().out.strip()
    assert "/v1.zip?share=" in out


def test_share_subcommand_signed_url_validates(tmp_path, capsys):
    (tmp_path / "doc.pdf").write_bytes(b"PDF")
    with patch(
        "sys.argv",
        ["neev", "share", str(tmp_path / "doc.pdf"), "-d", str(tmp_path), "--expires", "30"],
    ):
        main()
    captured = capsys.readouterr()
    # stderr carries the generated secret; parse it
    secret_hex = None
    for line in captured.err.splitlines():
        if "generated ephemeral one:" in line:
            secret_hex = line.split("generated ephemeral one:", 1)[1].split()[0]
            break
    assert secret_hex is not None
    secret = bytes.fromhex(secret_hex)
    token = captured.out.strip().split("?share=", 1)[1]
    payload = verify(token, secret)
    assert payload is not None
    assert payload.path == "/doc.pdf"
    assert payload.write_allowed is False


def test_share_subcommand_write_flag(tmp_path, capsys):
    (tmp_path / "up").mkdir()
    with patch(
        "sys.argv",
        ["neev", "share", str(tmp_path / "up"), "-d", str(tmp_path), "--expires", "60", "--write"],
    ):
        main()
    captured = capsys.readouterr()
    secret_hex = None
    for line in captured.err.splitlines():
        if "generated ephemeral one:" in line:
            secret_hex = line.split("generated ephemeral one:", 1)[1].split()[0]
            break
    assert secret_hex is not None
    secret = bytes.fromhex(secret_hex)
    token = captured.out.strip().split("?share=", 1)[1]
    payload = verify(token, secret)
    assert payload is not None
    assert payload.write_allowed is True


def test_share_subcommand_rejects_negative_expires(tmp_path):
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
    with (
        patch(
            "sys.argv",
            ["neev", "share", str(tmp_path / "nope"), "-d", str(tmp_path)],
        ),
        pytest.raises(SystemExit),
    ):
        main()
