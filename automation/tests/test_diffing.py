import pytest
from automation.diffing import normalize_config, diff_section


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


class TestDiffSections:
    def test_configs_empty_returns_empty_list(self):
        result = diff_section("", "")
        assert result["missing"] == []
        assert result["unmanaged"] == []

    def test_identical_configs_returns_empty_lists(self):
        line1 = "hello world"
        line2 = "hello world"
        result = diff_section(line1, line2)
        assert result["missing"] == []
        assert result["unmanaged"] == []

    def test_unmanaged_only_returns_unmanaged(self):
        text1 = "hello world\ni am sohaib mehdaoui"
        text2 = "hello world\ni am sohaib mehdaoui\nfourth year student"
        result = diff_section(text1, text2)
        assert result["missing"] == []
        assert result["unmanaged"] == ["fourth year student"]

    def test_missing_only_returns_missing(self):
        text1 = "hello world\ni am sohaib mehdaoui\nfourth year student"
        text2 = "hello world\ni am sohaib mehdaoui"
        result = diff_section(text1, text2)
        assert result["missing"] == ["fourth year student"]
        assert result["unmanaged"] == []

    def test_missing_and_unmanaged_returns_both(self):
        text1 = "hello world\ni am sohaib mehdaoui\nfourth year student"
        text2 = "hello world\ni am sohaib mehdaoui\nfrom casablanca"
        result = diff_section(text1, text2)
        assert result["missing"] == ["fourth year student"]
        assert result["unmanaged"] == ["from casablanca"]

    def test_duplicate_lines_dont_change_output(self):
        text1 = "hello world\nhello world"
        text2 = "hello world\nhello world\nhello world"
        result = diff_section(text1, text2)
        assert result["missing"] == []
        assert result["unmanaged"] == []

    def test_order_independence_returns_empty_lists(self):
        text1 = "hello world\ni am sohaib mehdaoui\nfourth year student"
        text2 = "fourth year student\nhello world\ni am sohaib mehdaoui"
        result = diff_section(text1, text2)
        assert result["missing"] == []
        assert result["unmanaged"] == []

    def test_indetation_whitespace_sensitivity(self):
        text1 = "hello world\ni am sohaib mehdaoui"
        text2 = "hello world\n i am sohaib mehdaoui"
        result = diff_section(text1, text2)
        assert result["missing"] == ["i am sohaib mehdaoui"]
        assert result["unmanaged"] == [" i am sohaib mehdaoui"]

    def test_both_configs_none_returns_empty_lists(self):
        result = diff_section(None, None)
        assert result["missing"] == []
        assert result["unmanaged"] == []
