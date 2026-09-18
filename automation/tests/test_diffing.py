import pytest

from automation.diffing import (
    normalize_config,
    diff_section,
    load_exceptions,
    filter_unmanaged,
)


class TestNormalizeConfig:
    def test_none_input_returns_empty_list(self):
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
            "hello world\n"
            "i am sohaib mehdaoui\n"
            "a 4th year network engineering student"
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

    def test_mixed_whitespace_with_blank_lines(self):
        text = (
            "hello world\r\n\n"
            " i am sohaib mehdaoui\n"
            "\ta 4th year network engineering student\t"
        )
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
        assert normalize_config(text) == [
            "hostname foo",
            "interface eth0",
        ]

    def test_single_line_without_trailing_newline(self):
        assert normalize_config("hostname foo") == ["hostname foo"]


class TestDiffSections:
    def test_empty_configs_return_empty_lists(self):
        result = diff_section("", "")
        assert result["missing"] == []
        assert result["unmanaged"] == []

    def test_identical_configs_return_empty_lists(self):
        result = diff_section("hello world", "hello world")
        assert result["missing"] == []
        assert result["unmanaged"] == []

    def test_unmanaged_only_returns_unmanaged(self):
        intended = "hello world\ni am sohaib mehdaoui"
        running = intended + "\nfourth year student"
        result = diff_section(intended, running)
        assert result["missing"] == []
        assert result["unmanaged"] == ["fourth year student"]

    def test_missing_only_returns_missing(self):
        intended = "hello world\ni am sohaib mehdaoui\nfourth year student"
        running = "hello world\ni am sohaib mehdaoui"
        result = diff_section(intended, running)
        assert result["missing"] == ["fourth year student"]
        assert result["unmanaged"] == []

    def test_missing_and_unmanaged_returns_both(self):
        intended = "hello world\ni am sohaib mehdaoui\nfourth year student"
        running = "hello world\ni am sohaib mehdaoui\nfrom casablanca"
        result = diff_section(intended, running)
        assert set(result["missing"]) == {"fourth year student"}
        assert set(result["unmanaged"]) == {"from casablanca"}

    def test_duplicate_lines_are_ignored_by_set_based_diff(self):
        intended = "hello world\nhello world"
        running = "hello world\nhello world\nhello world"
        result = diff_section(intended, running)
        assert result["missing"] == []
        assert result["unmanaged"] == []

    def test_order_independence_returns_empty_lists(self):
        intended = "hello world\ni am sohaib mehdaoui\nfourth year student"
        running = "fourth year student\nhello world\ni am sohaib mehdaoui"
        result = diff_section(intended, running)
        assert result["missing"] == []
        assert result["unmanaged"] == []

    def test_indentation_whitespace_sensitivity(self):
        intended = "hello world\ni am sohaib mehdaoui"
        running = "hello world\n i am sohaib mehdaoui"
        result = diff_section(intended, running)
        assert result["missing"] == ["i am sohaib mehdaoui"]
        assert result["unmanaged"] == [" i am sohaib mehdaoui"]

    def test_both_configs_none_return_empty_lists(self):
        result = diff_section(None, None)
        assert result["missing"] == []
        assert result["unmanaged"] == []

    def test_multiple_missing_lines_are_compared_as_sets(self):
        intended = "line1\nline2\nline3"
        running = "line1"
        result = diff_section(intended, running)
        assert set(result["missing"]) == {"line2", "line3"}
        assert result["unmanaged"] == []


class TestLoadExceptions:
    def test_file_does_not_exist_raises_file_not_found_error(self, tmp_path):
        missing_path = tmp_path / "missing.yaml"
        with pytest.raises(FileNotFoundError):
            load_exceptions(str(missing_path))

    def test_invalid_yaml_raises_value_error(self, tmp_path):
        bad_file = tmp_path / "bad_file.yaml"
        bad_file.write_text("interfaces: [unclosed_list\n")
        with pytest.raises(ValueError):
            load_exceptions(str(bad_file))

    def test_empty_yaml_returns_empty_dict(self, tmp_path):
        empty_file = tmp_path / "empty_file.yaml"
        empty_file.write_text("")
        assert load_exceptions(str(empty_file)) == {}

    def test_yaml_null_returns_empty_dict(self, tmp_path):
        null_file = tmp_path / "null.yaml"
        null_file.write_text("null\n")
        assert load_exceptions(str(null_file)) == {}

    def test_yaml_not_dictionary_raises_type_error(self, tmp_path):
        invalid_file = tmp_path / "invalid.yaml"
        invalid_file.write_text("- hello\n- world")
        with pytest.raises(TypeError):
            load_exceptions(str(invalid_file))

    def test_sections_is_none_returns_empty_set(self, tmp_path):
        empty_sections = tmp_path / "empty.yaml"
        empty_sections.write_text("interfaces:")
        assert load_exceptions(str(empty_sections)) == {"interfaces": set()}

    def test_empty_list_returns_empty_set(self, tmp_path):
        empty_list = tmp_path / "empty.yaml"
        empty_list.write_text("interfaces: []")
        assert load_exceptions(str(empty_list)) == {"interfaces": set()}

    def test_single_line_strings_return_set(self, tmp_path):
        normal_file = tmp_path / "normal_file.yaml"
        normal_file.write_text(
            "interfaces:\n" '  - "description test"\n' '  - "no shutdown"'
        )
        assert load_exceptions(str(normal_file)) == {
            "interfaces": {"description test", "no shutdown"}
        }

    def test_multiline_list_string_folds_without_separator(self, tmp_path):
        normal_file = tmp_path / "exceptions.yaml"
        normal_file.write_text('interfaces:\n  - "foo\\\nbar"\n')
        result = load_exceptions(str(normal_file))
        assert result == {"interfaces": {"foobar"}}

    def test_multiline_section_string_folds_without_separator(self, tmp_path):
        normal_file = tmp_path / "normal_file.yaml"
        normal_file.write_text('interfaces: "hello world\\\n i am sohaib"')
        result = load_exceptions(str(normal_file))
        assert result == {"interfaces": {"hello worldi am sohaib"}}

    def test_section_containing_non_string_raises_type_error(self, tmp_path):
        bad_file = tmp_path / "bad_file.yaml"
        bad_file.write_text("interfaces:\n  - 42")
        with pytest.raises(TypeError):
            load_exceptions(str(bad_file))

    def test_invalid_section_value_type_raises_type_error(self, tmp_path):
        bad_file = tmp_path / "bad_file.yaml"
        bad_file.write_text("interfaces:\n  interface1:\n    - hello")
        with pytest.raises(TypeError):
            load_exceptions(str(bad_file))

    def test_multiple_sections_with_multiple_types(self, tmp_path):
        good_file = tmp_path / "good_file.yaml"
        good_file.write_text(
            "interfaces:\n"
            '  - "interfaces1"\n'
            '  - "interface2"\n'
            'vlan: "vlan1\\\n'
            'vlan2"\n'
            'ospf: ""\n'
        )
        result = load_exceptions(str(good_file))
        assert result == {
            "interfaces": {"interfaces1", "interface2"},
            "vlan": {"vlan1vlan2"},
            "ospf": set(),
        }

    def test_blank_element_in_list_returns_normal_set(self, tmp_path):
        good_file = tmp_path / "good_file.yaml"
        good_file.write_text('interfaces:\n  - "interface1"\n  - ""')
        result = load_exceptions(str(good_file))
        assert result == {"interfaces": {"interface1"}}

    def test_section_with_single_line_string(self, tmp_path):
        good_file = tmp_path / "good_file.yaml"
        good_file.write_text('interfaces: "interface1"')
        result = load_exceptions(str(good_file))
        assert result == {"interfaces": {"interface1"}}


class TestFilterUnmanaged:
    def test_no_unmanaged_lines_returns_empty_list(self):
        assert filter_unmanaged([], {}, "interfaces") == []

    def test_filters_exception_lines(self):
        unmanaged = [
            "description test",
            "shutdown",
            "ip address 10.0.0.1",
        ]
        exceptions = {"interfaces": {"description test", "shutdown"}}
        result = filter_unmanaged(unmanaged, exceptions, "interfaces")
        assert result == ["ip address 10.0.0.1"]

    def test_unknown_section_returns_all_unmanaged_lines(self):
        unmanaged = ["line1", "line2"]
        assert filter_unmanaged(unmanaged, {}, "interfaces") == unmanaged

    def test_empty_exception_set_returns_all_unmanaged_lines(self):
        unmanaged = ["line1", "line2"]
        assert (
            filter_unmanaged(unmanaged, {"interfaces": set()}, "interfaces")
            == unmanaged
        )

    def test_exceptions_from_another_section_do_not_filter(self):
        unmanaged = ["description test", "shutdown"]
        exceptions = {"vlans": {"description test"}}
        result = filter_unmanaged(unmanaged, exceptions, "interfaces")
        assert result == unmanaged

    def test_all_lines_exempted_returns_empty_list(self):
        unmanaged = ["description test", "shutdown"]
        exceptions = {"interfaces": {"description test", "shutdown"}}
        result = filter_unmanaged(unmanaged, exceptions, "interfaces")
        assert result == []

    def test_duplicate_unmanaged_lines_each_filtered_independently(self):
        unmanaged = ["shutdown", "shutdown", "ip address 10.0.0.1"]
        exceptions = {"interfaces": {"shutdown"}}
        result = filter_unmanaged(unmanaged, exceptions, "interfaces")
        assert result == ["ip address 10.0.0.1"]

    def test_duplicate_unmanaged_lines_not_exempted_are_all_kept(self):
        unmanaged = ["ip address 10.0.0.1", "ip address 10.0.0.1"]
        exceptions = {"interfaces": {"shutdown"}}
        result = filter_unmanaged(unmanaged, exceptions, "interfaces")
        assert result == ["ip address 10.0.0.1", "ip address 10.0.0.1"]

    def test_result_preserves_original_order(self):
        unmanaged = ["c line", "a line", "shutdown", "b line"]
        exceptions = {"interfaces": {"shutdown"}}
        result = filter_unmanaged(unmanaged, exceptions, "interfaces")
        assert result == ["c line", "a line", "b line"]

    def test_case_sensitive_match_does_not_filter_different_case(self):
        unmanaged = ["Shutdown", "shutdown"]
        exceptions = {"interfaces": {"shutdown"}}
        result = filter_unmanaged(unmanaged, exceptions, "interfaces")
        assert result == ["Shutdown"]

    def test_whitespace_mismatch_does_not_filter(self):
        unmanaged = [" shutdown", "shutdown "]
        exceptions = {"interfaces": {"shutdown"}}
        result = filter_unmanaged(unmanaged, exceptions, "interfaces")
        assert result == [" shutdown", "shutdown "]

    def test_empty_string_section_behaves_like_unknown_section(self):
        unmanaged = ["line1", "line2"]
        exceptions = {"interfaces": {"line1"}}
        result = filter_unmanaged(unmanaged, exceptions, "")
        assert result == unmanaged

    def test_matching_section_selected_among_multiple_sections(self):
        unmanaged = ["description test", "shutdown", "ip address 10.0.0.1"]
        exceptions = {
            "interfaces": {"description test"},
            "vlans": {"shutdown", "ip address 10.0.0.1"},
            "bgp": {"ip address 10.0.0.1"},
        }
        result = filter_unmanaged(unmanaged, exceptions, "interfaces")
        assert result == ["shutdown", "ip address 10.0.0.1"]
