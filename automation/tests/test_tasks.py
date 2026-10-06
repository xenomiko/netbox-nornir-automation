import json
import pytest
from automation.tasks import atomic_json_writer, audit_task
from types import SimpleNamespace
from pathlib import Path


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
        result, report = run_audit(
            intended={"ntp": "ntp server 10.0.0.1"},
            running={"ntp": "ntp server 10.0.0.1"},
        )
        assert report["has_drift"] is False
        assert report["diffs"]["ntp"] == {"missing": [], "unmanaged": []}

    def test_drift_when_intended_doesnt_match_running(self, run_audit):
        result, report = run_audit(
            intended={"ntp": "ntp server 10.0.0.1"},
            running={"ntp": "ntp server 10.0.0.2"},
        )
        assert report["has_drift"] is True
        assert report["diffs"]["ntp"] == {
            "missing": ["ntp server 10.0.0.1"],
            "unmanaged": ["ntp server 10.0.0.2"],
        }
