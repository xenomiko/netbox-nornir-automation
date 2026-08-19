import argparse
import logging
import sys
import time
import uuid
import warnings
from typing import List, Optional

from automation.nornir_config import get_netbox_client, get_nornir
from automation.tasks import audit_task, remediate_task

warnings.filterwarnings("ignore")

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

for noisy_logger in (
    "nornir",
    "scrapli",
    "napalm",
    "paramiko",
    "netmiko",
    "urllib3",
    "pyeapi",
):
    logging.getLogger(noisy_logger).setLevel(logging.ERROR)

logger = logging.getLogger("automation.main")


def print_summary(summary_records: list, total_time: float):
    print("\n" + "=" * 70)
    print("                      AUTOMATION EXECUTION SUMMARY")
    print("=" * 70)
    print(f"Total Run Time: {total_time:.2f} seconds\n")
    print(f"{'DEVICE':<12} {'PLATFORM':<10} {'DRIFT DETECTED':<16} {'STATUS'}")
    print("-" * 70)

    for rec in summary_records:
        drift_str = str(rec["drift"])
        print(
            f"{rec['device']:<12} {rec['platform']:<10} {drift_str:<16} {rec['status']}"
        )

    print("=" * 70 + "\n")


def run_pipeline(
    host_filter: Optional[str] = None,
    dry_run: bool = True,
    audit_only: bool = False,
    target_sections: Optional[List[str]] = None,
):
    start_time = time.perf_counter()
    run_id = str(uuid.uuid4())[:8]

    nr = get_nornir()
    nb = get_netbox_client()

    if host_filter:
        nr = nr.filter(name=host_filter)

    if not nr.inventory.hosts:
        print(f"Error: No hosts matched the filter '{host_filter}'.")
        return

    summary_map = {}
    for h_name, h_obj in nr.inventory.hosts.items():
        summary_map[h_name] = {
            "device": h_name,
            "platform": h_obj.platform or "unknown",
            "drift": False,
            "status": "IN SYNC",
        }

    # Phase 1: Audit
    audit_results = nr.run(task=audit_task, nb=nb, run_id=run_id)

    drift_detected_hosts = []
    for host_name, result in audit_results.items():
        if result.failed:
            summary_map[host_name]["status"] = "AUDIT FAILED"
            continue

        has_drift = result.result.get("has_drift", False)
        report_path = result.result.get("report_path")
        summary_map[host_name]["drift"] = has_drift

        if has_drift:
            drift_detected_hosts.append((host_name, report_path))
            summary_map[host_name]["status"] = "DRIFT DETECTED"

    # Phase 2: Remediation
    if not audit_only and drift_detected_hosts:
        for host_name, report_path in drift_detected_hosts:
            single_host_nr = nr.filter(name=host_name)
            remediate_results = single_host_nr.run(
                task=remediate_task,
                report_path=report_path,
                expected_run_id=run_id,
                target_sections=target_sections,
                dry_run=dry_run,
            )
            for h, r in remediate_results.items():
                if r.failed:
                    summary_map[h]["status"] = "FAILED"
                else:
                    summary_map[h]["status"] = "DRY RUN" if dry_run else "SUCCESS"

    elapsed_time = time.perf_counter() - start_time
    print_summary(list(summary_map.values()), elapsed_time)


def main():
    parser = argparse.ArgumentParser(
        description="Nornir Network Configuration Audit & Remediation Pipeline"
    )
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Target specific host name (e.g. ceos1)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Execute live remediation (default is dry-run mode)",
    )
    parser.add_argument(
        "--audit-only",
        action="store_true",
        help="Run audit phase only without triggering remediation",
    )
    parser.add_argument(
        "--sections",
        nargs="+",
        default=None,
        help="Limit remediation to specific configuration sections",
    )

    args = parser.parse_args()
    dry_run = not args.apply

    run_pipeline(
        host_filter=args.host,
        dry_run=dry_run,
        audit_only=args.audit_only,
        target_sections=args.sections,
    )


if __name__ == "__main__":
    main()
