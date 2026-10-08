import json
import pytest
from automation.tasks import atomic_json_writer, audit_task, remediate_task
from types import SimpleNamespace
from pathlib import Path
from automation.renderer import CONFIG_SECTIONS
from automation.senders import napalm_senders


class TestAtomicJsonWriter:
    def test_writes_correct_data(self, tmp_path):
        target = tmp_path / "report.json"
        data = {"host": "ceos1", "has_drift": False}
        atomic_json_writer(target, data)
        assert json.loads(target.read_text(encoding="utf-8")) == data

    def test_overwrites_data(self, tmp_path):
        target = tmp_path / "report.json"
        target.write_text("Hello World", encoding="utf-8")
        data = {"host": "ceos1", "has_drift": False}
        atomic_json_writer(target, data)
        assert json.loads(target.read_text(encoding="utf-8")) == data

    def test_parent_directory_is_created(self, tmp_path):
        nested_dir = tmp_path / "nested" / "subfolder"
        target = nested_dir / "report.json"
        data = {"host": "ceos1", "has_drift": False}
        assert not nested_dir.exists()
        atomic_json_writer(target, data)
        assert nested_dir.exists()
        assert nested_dir.is_dir()
        assert target.exists()

    def test_no_leftover_files_left(self, tmp_path):
        target = tmp_path / "report.json"
        data = {"host": "ceos1", "has_drift": False}
        atomic_json_writer(target, data)
        assert list(tmp_path.iterdir()) == [target]

    def test_raises_type_error_on_unserializable_data(self, tmp_path):
        target = tmp_path / "report.json"
        bad_data = {"host": "ceos1", "sections": {"ntp", "snmp"}}  # a set
        with pytest.raises(TypeError):
            atomic_json_writer(target, bad_data)

    def test_temp_file_cleaned_up_on_failure(self, tmp_path):
        target = tmp_path / "report.json"
        bad_data = {"host": "ceos1", "sections": {"ntp", "snmp"}}
        with pytest.raises(TypeError):
            atomic_json_writer(target, bad_data)
        assert list(tmp_path.iterdir()) == []

    def test_existing_file_untouched_on_failure(self, tmp_path):
        target = tmp_path / "report.json"
        old_data = {"host": "ceos1", "has_drift": False}
        target.write_text(json.dumps(old_data), encoding="utf-8")
        bad_data = {"host": "ceos1", "sections": {"ntp", "snmp"}}
        with pytest.raises(TypeError):
            atomic_json_writer(target, bad_data)
        assert json.loads(target.read_text(encoding="utf-8")) == old_data
        assert list(tmp_path.iterdir()) == [target]


# testing the audit_task function
@pytest.fixture
def run_audit(tmp_path, monkeypatch):
    task = SimpleNamespace(host=SimpleNamespace(name="router1", platform="eos"))
    monkeypatch.setattr(
        "automation.tasks.build_device_config",
        lambda nb, task: "fake_device_config",
    )
    new_report_dir = tmp_path / "reports"
    monkeypatch.setattr("automation.tasks.REPORT_DIR", new_report_dir)

    def _run(intended, running, exceptions=None):
        monkeypatch.setattr(
            "automation.tasks.render_sections",
            lambda platform, device_config: intended,
        )
        monkeypatch.setattr(
            "automation.tasks.get_running_config",
            lambda task, sections: running,
        )
        monkeypatch.setattr("automation.tasks.EXCEPTIONS", exceptions or {})
        result = audit_task(task, None, "123456")
        report_path = result.result["report_path"]
        report = json.loads(Path(report_path).read_text(encoding="utf-8"))
        return result, report

    return _run


class TestAuditTask:
    def test_no_drift_when_intended_matches_running(self, run_audit):
        _, report = run_audit(
            intended={"ntp": "ntp server 10.0.0.1"},
            running={"ntp": "ntp server 10.0.0.1"},
        )
        assert report["has_drift"] is False
        assert report["diffs"]["ntp"] == {"missing": [], "unmanaged": []}

    def test_drift_when_intended_doesnt_match_running(self, run_audit):
        _, report = run_audit(
            intended={"ntp": "ntp server 10.0.0.1"},
            running={"ntp": "ntp server 10.0.0.2"},
        )
        assert report["has_drift"] is True
        assert report["diffs"]["ntp"] == {
            "missing": ["ntp server 10.0.0.1"],
            "unmanaged": ["ntp server 10.0.0.2"],
        }

    def test_allow_list_suppresses_diff_in_running(self, run_audit):
        _, report = run_audit(
            intended={"ntp": "ntp server 10.0.0.1"},
            running={"ntp": "ntp server 10.0.0.1\nntp server 10.0.0.9"},
            exceptions={"ntp": {"ntp server 10.0.0.9"}},
        )
        assert report["has_drift"] is False
        assert report["diffs"]["ntp"] == {"missing": [], "unmanaged": []}

    def test_doesnt_allow_list_suppresses_diff_in_intended(self, run_audit):
        _, report = run_audit(
            intended={"ntp": "ntp server 10.0.0.1\nntp server 10.0.0.9"},
            running={"ntp": "ntp server 10.0.0.1"},
            exceptions={"ntp": {"ntp server 10.0.0.9"}},
        )
        assert report["has_drift"] is True
        assert report["diffs"]["ntp"] == {
            "missing": ["ntp server 10.0.0.9"],
            "unmanaged": [],
        }

    def test_netbox_is_silent(self, run_audit):
        _, report = run_audit(
            intended={},
            running={"ntp": "ntp server 10.0.0.1"},
        )
        assert report["has_drift"] is True
        assert report["diffs"]["ntp"] == {
            "missing": [],
            "unmanaged": ["ntp server 10.0.0.1"],
        }

    def test_intended_and_running_both_missing(self, run_audit):
        _, report = run_audit(
            intended={},
            running={},
        )
        assert report["has_drift"] is False
        assert report["diffs"]["ntp"] == {
            "missing": [],
            "unmanaged": [],
        }

    def test_drift_in_one_section(self, run_audit):
        _, report = run_audit(
            intended={
                "ntp": "ntp server 10.0.0.1",
                "snmp": "snmp-server community public hello",
            },
            running={
                "ntp": "ntp server 10.0.0.2",
                "snmp": "snmp-server community public hello",
            },
        )
        assert report["has_drift"] is True
        assert report["diffs"]["ntp"] == {
            "missing": ["ntp server 10.0.0.1"],
            "unmanaged": ["ntp server 10.0.0.2"],
        }
        assert report["diffs"]["snmp"] == {
            "missing": [],
            "unmanaged": [],
        }

    def test_all_sections_are_present(self, run_audit):
        _, report = run_audit(
            intended={},
            running={},
        )
        assert set(report["diffs"]) == set(CONFIG_SECTIONS)

    def test_report_contains_metadata(self, run_audit):
        _, report = run_audit(
            intended={"ntp": "ntp server 10.0.0.1"},
            running={"ntp": "ntp server 10.0.0.1"},
        )
        assert report["run_id"] == "123456"
        assert report["host"] == "router1"
        assert report["platform"] == "eos"
        assert report["rendered_intended"] == {"ntp": "ntp server 10.0.0.1"}
        assert isinstance(report["timestamp"], float)

    def test_report_failed_is_false(self, run_audit):
        result, _ = run_audit(
            intended={"ntp": "ntp server 10.0.0.1"},
            running={"ntp": "ntp server 10.0.0.1"},
        )
        assert result.failed is False
        assert result.host.name == "router1"
        assert result.host.platform == "eos"
        assert result.result["run_id"] == "123456"

    def test_report_path_containes_needed_info(self, run_audit, tmp_path):
        result, _ = run_audit(
            intended={"ntp": "ntp server 10.0.0.1"},
            running={"ntp": "ntp server 10.0.0.1"},
        )
        report_path = Path(result.result["report_path"])
        assert report_path.suffix == ".json"
        assert "audit_router1_" in report_path.name
        assert "123456" in report_path.name
        assert report_path.parent == tmp_path / "reports"

    def test_result_and_report_hasdiff_are_equal_in_no_diff(self, run_audit):
        result, report = run_audit(
            intended={"ntp": "ntp server 10.0.0.1"},
            running={"ntp": "ntp server 10.0.0.1"},
        )
        assert result.result["has_drift"] is report["has_drift"]

    def test_result_and_report_hasdiff_are_equal_in_diff(self, run_audit):
        result, report = run_audit(
            intended={"ntp": "ntp server 10.0.0.1"},
            running={"ntp": "ntp server 10.0.0.2"},
        )
        assert result.result["has_drift"] is report["has_drift"]

    def test_getter_failure_propagates_and_writes_no_report(
        self, tmp_path, monkeypatch
    ):
        task = SimpleNamespace(host=SimpleNamespace(name="router1", platform="eos"))
        monkeypatch.setattr(
            "automation.tasks.build_device_config",
            lambda nb, task: "fake_device_config",
        )
        monkeypatch.setattr(
            "automation.tasks.render_sections",
            lambda platform, device_config: {"ntp": "ntp server 10.0.0.1"},
        )
        monkeypatch.setattr("automation.tasks.EXCEPTIONS", {})

        def failing_getter(task, sections):
            raise RuntimeError("device unreachable")

        monkeypatch.setattr("automation.tasks.get_running_config", failing_getter)
        new_report_dir = tmp_path / "reports"
        monkeypatch.setattr("automation.tasks.REPORT_DIR", new_report_dir)
        with pytest.raises(RuntimeError, match="device unreachable"):
            audit_task(task, None, run_id="123456")
        assert not new_report_dir.exists()


@pytest.fixture
def task():
    return SimpleNamespace(host=SimpleNamespace(name="router1", platform="eos"))


class TestRemediateTask:
    def test_report_file_not_found(self, tmp_path, task):
        file_path = tmp_path / "misssing.json"
        result = remediate_task(task, str(file_path), "1233")
        assert result.failed is True
        assert "Report file not found" in result.result

    def test_report_file_has_wrong_data_format(self, tmp_path, task):
        file_path = tmp_path / "false.json"
        file_path.write_text("interfaces: [unclosed_list\n")
        result = remediate_task(task, str(file_path), "1233")
        assert result.failed is True
        assert "Invalid audit report" in result.result

    def test_report_host_and_task_host_mismatch(self, tmp_path, task):
        report = {"host": "router2", "run_id": "123456"}
        file_path = tmp_path / "false.json"
        file_path.write_text(json.dumps(report))
        result = remediate_task(task, str(file_path), "123456")
        assert result.failed is True
        assert "Host mismatch!" in result.result

    def test_report_run_id_and_task_run_id_mismatch(self, tmp_path, task):
        report = {"host": "router1", "run_id": "12345"}
        file_path = tmp_path / "false.json"
        file_path.write_text(json.dumps(report))
        result = remediate_task(task, str(file_path), "123456")
        assert result.failed is True
        assert "Stale report!" in result.result

    def test_report_has_missing_fields(self, tmp_path, task):
        report = {"host": "router1", "run_id": "123456"}
        file_path = tmp_path / "false.json"
        file_path.write_text(json.dumps(report))
        result = remediate_task(task, str(file_path), "123456")
        assert result.failed is True
        assert "Invalid audit report: required fields are missing" in result.result

