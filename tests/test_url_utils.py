"""Regression tests for per-context encoding helpers (issue #101)."""

import json

from neev.url_utils import (
    encode_attr_url,
    is_valid_header_value,
    js_string_escape,
    quote_path,
    script_safe_json,
)


class TestQuotePath:
    def test_preserves_slashes(self):
        assert quote_path("/foo/bar/") == "/foo/bar/"

    def test_encodes_space(self):
        assert quote_path("/a b/") == "/a%20b/"

    def test_encodes_percent(self):
        assert quote_path("/a%b/") == "/a%25b/"

    def test_encodes_hash_and_question(self):
        assert quote_path("/a#b?c") == "/a%23b%3Fc"


class TestEncodeAttrUrl:
    def test_quote_and_escape(self):
        # `"` must never appear raw in an attribute value
        out = encode_attr_url('/a"b/')
        assert '"' not in out
        assert "%22" in out

    def test_ampersand_encoded(self):
        out = encode_attr_url("/a&b/")
        assert "&" not in out.replace("&amp;", "")
        assert "%26" in out


class TestJsStringEscape:
    def test_backslash_doubled(self):
        assert js_string_escape("a\\b") == "a\\\\b"

    def test_single_quote_escaped(self):
        assert js_string_escape("it's") == "it\\'s"

    def test_newline_escaped(self):
        assert js_string_escape("a\nb") == "a\\nb"


class TestScriptSafeJson:
    def test_script_tag_escaped(self):
        out = script_safe_json("</script>")
        assert "</script>" not in out
        assert "\\u003c" in out
        # still valid JSON
        assert json.loads(out) == "</script>"

    def test_ampersand_escaped(self):
        out = script_safe_json("a&b")
        assert "\\u0026" in out
        assert json.loads(out) == "a&b"


class TestIsValidHeaderValue:
    def test_plain_ok(self):
        assert is_valid_header_value("/foo/bar")

    def test_cr_rejected(self):
        assert not is_valid_header_value("/foo\rbar")

    def test_lf_rejected(self):
        assert not is_valid_header_value("/foo\nbar")

    def test_nul_rejected(self):
        assert not is_valid_header_value("/foo\x00bar")
