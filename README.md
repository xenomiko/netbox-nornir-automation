# Network Source-of-Truth & Config Drift Automation

[![CI](https://github.com/xenomiko/netbox-nornir-automation/actions/workflows/ci.yml/badge.svg)](https://github.com/xenomiko/netbox-nornir-automation/actions/workflows/ci.yml)

NetBox as the single source of truth, plus a Nornir pipeline that audits real devices against it, reports config drift, and can remediate it. Multi-vendor (Arista EOS, Cisco IOS, Aruba AOS-CX), dry-run by default.

## How It Works

1. **NetBox bootstrap** (`netbox/`): loads a YAML description of the lab (sites, devices, interfaces, IPs, cables, VLANs, config contexts) into NetBox via its API. Idempotent, so it is safe to re-run.
2. **Audit** (`automation/`): for each device, renders the *intended* config from NetBox with per-vendor Jinja2 templates, pulls the *running* config over Scrapli, and diffs the two section by section.
3. **Remediate** (optional): pushes the intended config for drifted sections, through NAPALM (EOS) or Scrapli (IOS, AOS-CX), then saves it.

```
netbox.yaml ──▶ NetBox ──▶ Nornir inventory
                              │
        build config (builders) ──▶ render (Jinja2) ──┐
        get running config (Scrapli) ─────────────────┴──▶ diff ──▶ audit report
                                                              │
                                              drift? ──▶ remediate ──▶ remediation report
```

Managed sections: `hostname`, `interfaces`, `vlans`, `ntp`, `snmp`, `ospf`, `management`, `security`, `static_routes`.

## Safety

- **Dry-run by default.** Nothing is pushed without `--apply`.
- **Audit-then-remediate.** Remediation only replays a freshly generated audit report.
- **Report integrity checks.** The report's `host` and `run_id` must match the device and run, so a stale report is never replayed.
- **Exceptions allowlist** (`automation/exceptions.yaml`) filters known-safe lines such as vendor defaults.
- **Scoping** with `--sections` and `--audit-only` limits the blast radius.
- **Atomic report writes** prevent corrupted reports after a crash.

## Setup

```bash
pip install -r requirements.txt

# .env in the project root
NB_URL=http://localhost:8000
NB_TOKEN=your_netbox_api_token
NETBOX_DEV_USER=your_device_ssh_username
NETBOX_DEV_PASS=your_device_ssh_password

sudo containerlab deploy -t topology.clab.yaml   # lab: 3x cEOS, 1x vIOS, 1x AOS-CX
python -m netbox.main                            # populate NetBox from netbox/netbox.yaml
```

## Usage

```bash
python -m automation.main --audit-only                  # report drift only
python -m automation.main                               # audit + dry-run remediation
python -m automation.main --apply                       # audit + live remediation
python -m automation.main --host ceos1 --apply          # one device
python -m automation.main --apply --sections ntp snmp   # specific sections
```

Reports are written to `automation/reports/` as `audit_<host>_<ts>_<run_id>.json` and `remediation_<host>_<ts>_<run_id>.json`, sharing a `run_id` for a verifiable audit trail.

Example summary:

```
DEVICE       PLATFORM   DRIFT DETECTED   STATUS
ceos1        eos        True             SUCCESS
ceos2        eos        False            IN SYNC
vios1        ios        True             DRY RUN
```

## Diff Engine

Each section's intended and running config are normalized into sets of trimmed, non-empty lines. `missing` (intended but absent) is drift that remediation pushes. `unmanaged` (present but not intended) is reported after filtering through `exceptions.yaml`. It is line-based and order-insensitive, simple and fast, but whitespace-sensitive and not a structural config parser.

## Development

```bash
pip install -r requirements-dev.txt
black automation netbox
ruff check automation netbox
pytest automation/tests --cov=automation -q
```

CI (GitHub Actions) runs black, ruff, and pytest with coverage on Python 3.10, 3.11, and 3.12 for every push and pull request. The suite has 344 tests covering builders, rendering, the diff engine, getters, senders, and tasks.

## Project Structure

```
netbox/          NetBox bootstrap: netbox.yaml, schemas, sync logic, Postman collection
automation/
  builders.py    NetBox data to validated DeviceConfig
  renderer.py    Jinja2 rendering (templates/{arista,cisco,aruba}/)
  getters/       running-config retrieval (Scrapli)
  senders/       config push (NAPALM, Scrapli)
  diffing.py     set-based diff and exceptions filtering
  tasks.py       audit_task / remediate_task
  main.py        CLI entry point
  tests/         pytest suite
topology.clab.yaml   Containerlab lab topology
```

## Stack

NetBox, Pynetbox, Nornir (NetBoxInventory2), Scrapli, NAPALM, Jinja2, Pydantic, Containerlab, pytest, black, ruff, GitHub Actions.

## Impact

A full audit of the 5-device lab (all nine sections) takes about 20 seconds. Doing it by hand (`show running-config` on each device, compared against notes) would take 15 to 20 minutes, and this scales by adding devices to NetBox rather than adding checklist time.

## Status and Roadmap

**Working end to end in the lab:** NetBox bootstrap, multi-vendor audit with exceptions filtering, dry-run and live remediation, report integrity checks, unit tests, and CI.

**Next:**
- Tests for the `netbox/` sync layer (CI currently covers `automation/` only)
- Structured, config-aware diffing to cut false positives from harmless line-order differences
- Scheduled, unattended audits and drift alerts (Slack, email)
- More platforms and more NetBox object types (circuits, racks, power)