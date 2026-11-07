from types import SimpleNamespace

import pytest

from automation.senders.napalm_senders import (
    napalm_cli,
    napalm_configure,
    push_config,
    save_config,
)


class FakeTask:
    def __init__(self, output=None, diff="", exc=None):
        self.host = SimpleNamespace(name="router1", platform="eos")
        self.output = output
        self.diff = diff
        self.exc = exc
        self.calls = []

    def run(self, **kwargs):
        self.calls.append(kwargs)
        if self.exc:
            raise self.exc
        return [SimpleNamespace(result=self.output, diff=self.diff)]


@pytest.fixture
def task():
    return FakeTask()


class TestPushConfig:
    @pytest.mark.parametrize("empty_config", ["", "   ", "\n\n", "\t \r\n", None])
    def test_empty_config_is_a_noop(self, empty_config):
        task = FakeTask()
        result = push_config(task, "ntp", empty_config)
        assert result.failed is False
        assert "No config to push for section 'ntp'" in result.result
        assert task.calls == []

    def test_empty_config_logs_warning(self, caplog):
        task = FakeTask()
        push_config(task, "ntp", "")
        assert "router1" in caplog.text
        assert "No config to push for section 'ntp'" in caplog.text

    @pytest.mark.parametrize("dry_run", [True, False])
    def test_napalm_configure_called_with_expected_arguments(self, dry_run):
        task = FakeTask()
        config_text = "ntp server 10.0.0.1\n  ntp server 10.0.0.2\n"
        push_config(task, "ntp", config_text, dry_run=dry_run)
        assert len(task.calls) == 1
        assert task.calls[0] == {
            "task": napalm_configure,
            "configuration": config_text,
            "replace": False,
            "dry_run": dry_run,
        }

    def test_dry_run_defaults_to_true(self):
        task = FakeTask()
        push_config(task, "ntp", "ntp server 10.0.0.1")
        assert task.calls[0]["dry_run"] is True

    def test_diff_is_returned_and_marks_changed(self):
        diff = "+ntp server 10.0.0.1"
        task = FakeTask(diff=diff)
        result = push_config(task, "ntp", "ntp server 10.0.0.1")
        assert result.failed is False
        assert result.result == diff
        assert result.diff == diff
        assert result.changed is True
        assert result.host is task.host

    @pytest.mark.parametrize("empty_diff", ["", None])
    def test_no_diff_returns_placeholder_and_not_changed(self, empty_diff):
        task = FakeTask(diff=empty_diff)
        result = push_config(task, "ntp", "ntp server 10.0.0.1")
        assert result.failed is False
        assert result.result == "(no changes)"
        assert result.diff == "(no changes)"
        assert result.changed is False

    def test_exception_returns_failed_result(self):
        task = FakeTask(exc=RuntimeError("eapi unreachable"))
        result = push_config(task, "ntp", "ntp server 10.0.0.1")
        assert result.failed is True
        assert "NAPALM push failed for section 'ntp'" in result.result
        assert "eapi unreachable" in result.result

    def test_exception_is_logged(self, caplog):
        task = FakeTask(exc=RuntimeError("boom"))
        push_config(task, "snmp", "snmp-server community public ro")
        assert "router1" in caplog.text
        assert "snmp" in caplog.text
        assert "boom" in caplog.text


class TestSaveConfig:
    def test_runs_write_memory_through_napalm_cli(self, task):
        save_config(task)
        assert len(task.calls) == 1
        assert task.calls[0] == {
            "task": napalm_cli,
            "commands": ["write memory"],
        }

    def test_success_returns_device_output(self):
        task = FakeTask(output="Copy completed successfully.")
        result = save_config(task)
        assert result.failed is False
        assert result.result == "Copy completed successfully."
        assert result.host is task.host

    def test_dict_output_is_passed_through_unchanged(self):
        output = {"write memory": "Copy completed successfully."}
        task = FakeTask(output=output)
        result = save_config(task)
        assert result.failed is False
        assert result.result == output

    def test_exception_returns_failed_result(self):
        task = FakeTask(exc=RuntimeError("save exploded"))
        result = save_config(task)
        assert result.failed is True
        assert "NAPALM save failed" in result.result
        assert "save exploded" in result.result

    def test_exception_is_logged(self, caplog):
        task = FakeTask(exc=RuntimeError("boom"))
        save_config(task)
        assert "router1" in caplog.text
        assert "boom" in caplog.text
