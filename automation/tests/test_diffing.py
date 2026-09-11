import pytest
from automation.diffing import normalize_config


class TestNormalizeConfig:
    def test_none_input_empty_lists(self):
        assert normalize_config(None) == []

    def test_empty_string_returns_empty_list(self):
        assert normalize_config("") == []

    def test_whitespace_only_string_returns_empty_list(self):
        assert normalize_config("    ") == []
        assert normalize_config("\r\r\r") == []
        assert normalize_config("\n\n\n") == []
        assert normalize_config("\t\t") == []

    def test_normal_lines(self):
        text = (
            "hello world\ni am sohaib mehdaoui\na 4th year network engineering student"
        )
        assert normalize_config(text) == [
            "hello world",
            "i am sohaib mehdaoui",
            "a 4th year network engineering student",
        ]

    def test_leading_spaces_preserved(self):
        assert normalize_config(" hello world") == [" hello world"]

    def test_leading_tabs_preserved(self):
        assert normalize_config("\thello world") == ["\thello world"]

    def test_trailing_spaces_removed(self):
        assert normalize_config("hello world ") == ["hello world"]

    def test_trailing_tabs_removed(self):
        assert normalize_config("hello world\t") == ["hello world"]

    def test_mixed_leading_and_trailing_whitespace_with_blank_lines(self):
        text = "hello world\r\n\n i am sohaib mehdaoui\n\ta 4th year network engineering student\t"
        assert normalize_config(text) == [
            "hello world",
            " i am sohaib mehdaoui",
            "\ta 4th year network engineering student",
        ]

    def test_duplicate_lines_unchanged(self):
        assert normalize_config("hello world\nhello world") == [
            "hello world",
            "hello world",
        ]

    def test_windows_line_endings(self):
        text = "hostname foo\r\ninterface eth0\r\n"
        assert normalize_config(text) == ["hostname foo", "interface eth0"]

    def test_single_line_without_trailing_newline(self):
        assert normalize_config("hostname foo") == ["hostname foo"]
