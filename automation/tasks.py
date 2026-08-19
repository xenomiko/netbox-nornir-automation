from .getters.scrapli_getters import get_running_config
from .builders import build_device_config
from .renderer import render_sections, CONFIG_SECTIONS
from .diffing import filter_unmanaged, diff_section, load_exceptions
import logging
import os
import tempfile
import time
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from nornir.core.task import Task, Result

logger = logging.getLogger(__name__)
REPORT_DIR = Path("reports")
EXCEPTIONS_FILE = "exceptions.yaml"
try:
    EXCEPTIONS = load_exceptions(EXCEPTIONS_FILE)
except FileNotFoundError:
    raise


def atomic_json_writer(file_path: Path, data: Dict[str, Any]) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temp_fd, temp_path = tempfile.mkstemp(dir=file_path.parent, suffix="tmp")
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(temp_path, file_path)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


def audit_task(task: Task, nb: Any, run_id: str = None) -> Result:
    host_name = task.host.name
    platform = task.host.platform
    device_config = build_device_config(nb, task)
    rendered_sections = render_sections(platform, device_config)
    running_sections = get_running_config(task, CONFIG_SECTIONS)
    diffs: Dict[str, Dict[str, List[str]]] = {}
    has_drift = False
    for section in CONFIG_SECTIONS:
        intended = rendered_sections.get(section, "")
        running = running_sections.get(section, "")
        raw_diff = diff_section(intended, running)
        filtered_unmanaged = filter_unmanaged(
            raw_diff["unmanaged"], EXCEPTIONS, section
        )
        missing = raw_diff["missing"]
        if missing or filtered_unmanaged:
            has_drift = True
        diffs[section] = {
            "missing": missing,
            "unmanaged": filtered_unmanaged,
        }
    report_data = {
        "run_id": run_id,
        "host": host_name,
        "platform": platform,
        "timestamp": time.time(),
        "has_drift": has_drift,
        "diffs": diffs,
        "rendered_intended": rendered_sections,
    }
    report_path = REPORT_DIR / f"audit_{run_id}_{host_name}.json"
    atomic_json_writer(report_path, report_data)
    return Result(
        host=task.host,
        failed=False,
        result={
            "has_drift": has_drift,
            "report_path": str(report_path),
            "run_id": run_id,
        },
    )


def remediate_task(
    task: Task,
    report_path: str,
    expected_run_id: str,
    target_sections: Optional[List[str]] = None,
    dry_run: bool = True,
) -> Result:
    host_name = task.host.name
    file_p = Path(report_path)
    if not file_p.is_file():
        msg = f"Report file not found: {report_path}"
        return Result(
            host=task.host,
            failed=True,
            result=msg,
        )
    try:
        with file_p.open("r", encoding="utf-8") as f:
            report_data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        msg = f"Invalid audit report '{report_path}': {e}"
        return Result(
            host=task.host,
            failed=True,
            result=msg,
        )
    if report_data.get("host") != host_name:
        msg = (
            f"Host mismatch! "
            f"File host: {report_data.get('host')}, "
            f"Target host: {host_name}"
        )
        return Result(
            host=task.host,
            failed=True,
            result=msg,
        )
    if report_data.get("run_id") != expected_run_id:
        msg = (
            f"Stale report! "
            f"File run_id: {report_data.get('run_id')}, "
            f"Expected: {expected_run_id}"
        )
        return Result(
            host=task.host,
            failed=True,
            result=msg,
        )
    if "diffs" not in report_data or "rendered_intended" not in report_data:
        msg = "Invalid audit report: required fields are missing."
        return Result(
            host=task.host,
            failed=True,
            result=msg,
        )
    platform = task.host.platform
    if platform == "aoscx":
        from .senders import scrapli_senders as sender
    elif platform in ("eos", "ios"):
        from .senders import napalm_senders as sender
    else:
        msg = f"Unsupported platform for remediation: {platform}"
        return Result(
            host=task.host,
            failed=True,
            result=msg,
        )
    sections_to_process = (
        target_sections
        if target_sections is not None
        else list(report_data["diffs"].keys())
    )
    pushed_sections: Dict[str, Any] = {}
    for section in sections_to_process:
        missing_lines = report_data["diffs"].get(section, {}).get("missing", [])
        intended_text = report_data["rendered_intended"].get(section, "")
        if not missing_lines and not intended_text:
            continue
        try:
            push_res = sender.push_config(
                task=task,
                section=section,
                config_text=intended_text,  # Pushing full section block
                dry_run=dry_run,
            )
            pushed_sections[section] = {
                "success": not push_res.failed,
                "output": push_res.result,
            }
        except Exception as e:
            pushed_sections[section] = {
                "success": False,
                "error": str(e),
            }
    remediation_summary = {
        "run_id": expected_run_id,
        "host": host_name,
        "platform": platform,
        "dry_run": dry_run,
        "timestamp": time.time(),
        "applied_sections": pushed_sections,
    }
    audit_log_path = REPORT_DIR / f"remediation_{expected_run_id}_{host_name}.json"
    atomic_json_writer(
        audit_log_path,
        remediation_summary,
    )
    has_failures = any(
        not section_result.get("success", False)
        for section_result in pushed_sections.values()
    )
    return Result(
        host=task.host,
        failed=has_failures,
        result={
            "summary": (
                f"Remediation executed "
                f"(dry_run={dry_run}). "
                f"Log written to {audit_log_path}"
            ),
            "audit_trail": str(audit_log_path),
            "details": pushed_sections,
        },
    )
