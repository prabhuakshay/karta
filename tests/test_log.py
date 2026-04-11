"""Tests for neev.log — ANSI styling and status coloring."""

from unittest.mock import patch

from neev.log import ansi_styled, status_color


# -- ANSI styling ------------------------------------------------------------


class TestAnsiStyled:
    def test_plain_when_not_tty(self):
        with patch("sys.stderr.isatty", return_value=False):
            assert ansi_styled("text", "32") == "text"

    def test_styled_when_tty(self):
        with patch("sys.stderr.isatty", return_value=True):
            assert ansi_styled("text", "32") == "\033[32mtext\033[0m"


class TestStatusColor:
    def test_2xx_green(self):
        with patch("sys.stderr.isatty", return_value=True):
            result = status_color(200)
            assert "\033[32m" in result

    def test_3xx_yellow(self):
        with patch("sys.stderr.isatty", return_value=True):
            result = status_color(301)
            assert "\033[33m" in result

    def test_4xx_red(self):
        with patch("sys.stderr.isatty", return_value=True):
            result = status_color(404)
            assert "\033[31m" in result

    def test_5xx_red(self):
        with patch("sys.stderr.isatty", return_value=True):
            result = status_color(500)
            assert "\033[31m" in result
