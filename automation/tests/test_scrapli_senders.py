from types import SimpleNamespace

import pytest
from nornir.core.exceptions import NornirSubTaskError
from scrapli.exceptions import ScrapliException

from automation.senders.scrapli_senders import (
    _split_config_lines,
    push_config,
    save_config,
    send_command,
    send_configs,
)


class FakeHost:
    def __init__(self, platform="ios"):
        self.name = "router1"
        self.platform = platform
        self.close_calls = 0

    def close_connections(self):
        self.close_calls += 1


class FakeTask:
    def __init__(self, platform="ios", output="device output", failed=False, exc=None):
        self.host = FakeHost(platform)
        self.output = output
        self.failed = failed
        self.exc = exc
        self.calls = []

    def run(self, **kwargs):
        self.calls.append(kwargs)
        if self.exc:
            raise self.exc
        return [SimpleNamespace(result=self.output, failed=self.failed)]


def make_subtask_error(**result_attrs):
    return NornirSubTaskError(
        task=SimpleNamespace(name="send_configs"),
        result=SimpleNamespace(**result_attrs),
    )


@pytest.fixture
def task():
    return FakeTask()


class TestSplitConfigLines:
    def test_empty_string_returns_empty_list(self):
        assert _split_config_lines("") == []

    def test_blank_lines_are_dropped(self):
        assert _split_config_lines("\n\n   \n\t\n") == []

    @pytest.mark.parametrize("separator", ["!", "  !  ", "\t!"])
    def test_bang_only_lines_are_dropped(self, separator):
        assert _split_config_lines(f"{separator}\nhostname r1") == ["hostname r1"]

    def test_indentation_and_trailing_whitespace_are_stripped(self):
        text = "interface Gi0/1\n   description uplink  \n\tno shutdown\t"
        assert _split_config_lines(text) == [
            "interface Gi0/1",
            "description uplink",
            "no shutdown",
        ]

    def test_order_and_duplicates_are_preserved(self):
        text = "ntp server 10.0.0.2\nntp server 10.0.0.1\nntp server 10.0.0.2"
        assert _split_config_lines(text) == [
            "ntp server 10.0.0.2",
            "ntp server 10.0.0.1",
            "ntp server 10.0.0.2",
        ]

    def test_windows_line_endings(self):
        assert _split_config_lines("hostname r1\r\n!\r\nntp server 1.1.1.1\r\n") == [
            "hostname r1",
            "ntp server 1.1.1.1",
        ]


class TestPushConfig:
    @pytest.mark.parametrize("empty_config", ["", "   ", "\n\n", None])
    def test_empty_config_is_a_noop(self, empty_config):
        task = FakeTask()
        result = push_config(task, "ntp", empty_config, dry_run=False)
        assert result.failed is False
        assert "No config to push for section 'ntp'" in result.result
        assert task.calls == []

    def test_config_with_only_separators_is_a_noop(self):
        task = FakeTask()
        result = push_config(task, "ntp", "!\n  \n!\n", dry_run=False)
        assert result.failed is False
        assert "Nothing to send for section 'ntp'" in result.result
        assert task.calls == []

    def test_noop_cases_log_warning(self, caplog):
        task = FakeTask()
        push_config(task, "ntp", "")
        push_config(task, "snmp", "!")
        assert "No config to push for section 'ntp'" in caplog.text
        assert "Nothing to send for section 'snmp'" in caplog.text

    def test_dry_run_returns_preview_without_touching_device(self):
        task = FakeTask()
        config_text = "ntp server 10.0.0.1\n!\n  ntp server 10.0.0.2\n"
        result = push_config(task, "ntp", config_text, dry_run=True)
        expected = "ntp server 10.0.0.1\nntp server 10.0.0.2"
        assert task.calls == []
        assert result.failed is False
        assert result.result == expected
        assert result.diff == expected
        assert result.changed is False

    def test_dry_run_defaults_to_true(self):
        task = FakeTask()
        result = push_config(task, "ntp", "ntp server 10.0.0.1")
        assert task.calls == []
        assert result.changed is False

    def test_live_run_sends_normalized_commands(self):
        task = FakeTask()
        config_text = "interface Gi0/1\n   description uplink\n!\n   no shutdown\n"
        push_config(task, "interfaces", config_text, dry_run=False)
        assert len(task.calls) == 1
        assert task.calls[0] == {
            "task": send_configs,
            "configs": ["interface Gi0/1", "description uplink", "no shutdown"],
            "stop_on_failed": False,
        }

    def test_live_run_success_returns_device_output(self):
        task = FakeTask(output="applied ok")
        result = push_config(task, "ntp", "ntp server 10.0.0.1", dry_run=False)
        assert result.failed is False
        assert result.result == "applied ok"
        assert result.diff == "applied ok"
        assert result.changed is True
        assert result.host is task.host
        assert task.host.close_calls == 0

    def test_live_run_device_reported_failure_is_not_changed(self):
        task = FakeTask(output="% Invalid input", failed=True)
        result = push_config(task, "ntp", "ntp server bad", dry_run=False)
        assert result.failed is True
        assert result.result == "% Invalid input"
        assert result.changed is False

    def test_nornir_subtask_error_uses_scrapli_output_as_detail(self):
        exc = make_subtask_error(result="% Invalid input", exception=None)
        task = FakeTask(exc=exc)
        result = push_config(task, "ntp", "ntp server bad", dry_run=False)
        assert result.failed is True
        assert "Failed to push section 'ntp'" in result.result
        assert "% Invalid input" in result.result
        assert task.host.close_calls == 1

    def test_nornir_subtask_error_falls_back_to_exception_detail(self):
        exc = make_subtask_error(result=None, exception=ValueError("auth failed"))
        task = FakeTask(exc=exc)
        result = push_config(task, "ntp", "ntp server bad", dry_run=False)
        assert result.failed is True
        assert "auth failed" in result.result
        assert task.host.close_calls == 1

    def test_scrapli_exception_returns_failed_result(self):
        task = FakeTask(exc=ScrapliException("timeout"))
        result = push_config(task, "ntp", "ntp server 10.0.0.1", dry_run=False)
        assert result.failed is True
        assert "Scrapli error pushing section 'ntp'" in result.result
        assert "timeout" in result.result
        assert task.host.close_calls == 1

    def test_generic_exception_includes_exception_type(self):
        task = FakeTask(exc=RuntimeError("boom"))
        result = push_config(task, "ntp", "ntp server 10.0.0.1", dry_run=False)
        assert result.failed is True
        assert "Failed to push section 'ntp'" in result.result
        assert "RuntimeError: boom" in result.result
        assert task.host.close_calls == 1

    def test_failure_is_logged(self, caplog):
        task = FakeTask(exc=RuntimeError("boom"))
        push_config(task, "ntp", "ntp server 10.0.0.1", dry_run=False)
        assert "router1" in caplog.text
        assert "boom" in caplog.text

    def test_dry_run_does_not_close_connections(self):
        task = FakeTask()
        push_config(task, "ntp", "ntp server 10.0.0.1", dry_run=True)
        assert task.host.close_calls == 0


class TestSaveConfig:
    @pytest.mark.parametrize("platform", ["ios", "aoscx"])
    def test_supported_platforms_run_write_memory(self, platform):
        task = FakeTask(platform=platform, output="Building configuration...")
        result = save_config(task)
        assert len(task.calls) == 1
        assert task.calls[0] == {"task": send_command, "command": "write memory"}
        assert result.failed is False
        assert result.result == "Building configuration..."
        assert result.host is task.host

    def test_unsupported_platform_is_a_noop(self):
        task = FakeTask(platform="eos")
        result = save_config(task)
        assert result.failed is False
        assert "No save command defined for platform 'eos'" in result.result
        assert task.calls == []

    def test_unsupported_platform_logs_warning(self, caplog):
        task = FakeTask(platform="junos")
        save_config(task)
        assert "router1" in caplog.text
        assert "junos" in caplog.text

    def test_nornir_subtask_error_uses_sub_result_detail(self):
        exc = make_subtask_error(result="% Permission denied")
        task = FakeTask(exc=exc)
        result = save_config(task)
        assert result.failed is True
        assert "Failed to save configuration" in result.result
        assert "% Permission denied" in result.result
        assert task.host.close_calls == 1

    def test_nornir_subtask_error_falls_back_to_exception_attribute(self):
        exc = make_subtask_error(exception=ValueError("channel closed"))
        task = FakeTask(exc=exc)
        result = save_config(task)
        assert result.failed is True
        assert "channel closed" in result.result
        assert task.host.close_calls == 1

    def test_scrapli_exception_returns_failed_result(self):
        task = FakeTask(exc=ScrapliException("timeout"))
        result = save_config(task)
        assert result.failed is True
        assert "Scrapli error saving configuration" in result.result
        assert "timeout" in result.result
        assert task.host.close_calls == 1

    def test_generic_exception_includes_exception_type(self):
        task = FakeTask(exc=RuntimeError("boom"))
        result = save_config(task)
        assert result.failed is True
        assert "Failed to save configuration" in result.result
        assert "RuntimeError: boom" in result.result
        assert task.host.close_calls == 1

    def test_failure_is_logged(self, caplog):
        task = FakeTask(exc=RuntimeError("boom"))
        save_config(task)
        assert "router1" in caplog.text
        assert "boom" in caplog.text
