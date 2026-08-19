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


