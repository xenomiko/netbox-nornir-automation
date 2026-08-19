# Network Source-of-Truth & Config Drift Automation

> Replaces manual, per-device SSH configuration with an automated, auditable pipeline that treats NetBox as the single source of truth.

A lab project that turns **NetBox** into a Source of Truth for a small multi-vendor network, and then uses **Nornir** to continuously check whether the real devices match what NetBox says they should look like — and fix them automatically when they don't.

If you're technical: this is a NetBox bootstrap tool + a Jinja2-templated, multi-vendor config-drift audit/remediation pipeline built on Nornir, Scrapli, and NAPALM.

If you're not: think of it as a robot that reads a "master plan" of how the network should be configured, walks around checking every device against that plan, writes a report of anything that doesn't match, and — if you tell it to — quietly fixes it.

---

## 1. The Problem

Network configuration usually lives in one of two bad places:

- **In someone's head / a spreadsheet** — nobody is 100% sure what a device's config *should* be, only what it currently *is*.
- **Only on the device itself** — if a device is misconfigured by hand ("just this once, temporarily"), nothing ever notices or corrects it. Config drift accumulates silently until it causes an outage.

Manually logging into every switch and router to check and fix these differences doesn't scale, is error-prone, and gets skipped when people are busy.

## 2. What It Does

This project is really two connected tools:

1. **NetBox Bootstrap** (`netbox/`) — Reads a single YAML file describing the intended network (sites, devices, interfaces, IPs, cables, VLANs, config contexts) and pushes it into NetBox via its REST API. Safe to re-run any time; it only creates or updates what's changed.
2. **Audit & Remediation Pipeline** (`automation/`) — Pulls live inventory and settings straight out of NetBox, renders the *intended* configuration for each device in its own vendor syntax, connects to the real device, pulls its *running* configuration, and **diffs the two**. Anything intended-but-missing is reported as drift. If asked to, the pipeline can then push just the missing lines back onto the device.

In short: **NetBox says what should be true. The pipeline checks what is true, and can make it true.**

## 3. Architecture

```
netbox.yaml  ──▶  netbox_services.py  ──▶  NetBox (Source of Truth)
                                                │
                                                ▼
                                   Nornir inventory (NetBoxInventory2)
                                                │
                     ┌──────────────────────────┴──────────────────────────┐
                     ▼                                                     ▼
        build_device_config() (builders.py)                  get_running_config() (getters/)
        pulls config context + interfaces/                    connects via Scrapli, pulls
        vlans from NetBox, validates with Pydantic             the live running-config
                     │                                                     │
                     ▼                                                     │
        render_sections() (renderer.py)                                   │
        renders per-platform Jinja2 templates                             │
        into "intended" config text                                      │
                     │                                                     │
                     └───────────────▶  diff_section() (diffing.py)  ◀─────┘
                                                │
                                    audit_<host>_<ts>.json report
                                     (missing / unmanaged lines)
                                                │
                                     drift found? ──▶ remediate_task()
                                                │           │
                                                │      push_config() via
                                                │      NAPALM (EOS) or
                                                │      Scrapli (IOS/AOS-CX)
                                                │           │
                                                ▼           ▼
                                   remediation_<host>_<ts>.json report
```

A parallel `topology.clab.yaml` spins up the actual lab (3× Arista cEOS, 1× Cisco vIOS, 1× Aruba AOS-CX) using Containerlab, so the pipeline has real devices to talk to. A Postman collection is included for manually poking at the NetBox API while building this out.

## 4. Safety First

Nothing here touches a live device without several guardrails:

- **Dry-run by default.** `python -m automation.main` only *simulates* changes. You must explicitly pass `--apply` to push real config.
- **Audit-then-remediate, never blind push.** Remediation only ever replays a specific, freshly-generated audit report — it never improvises.
- **Report integrity checks.** Before remediating, the pipeline verifies the report's `host` and `run_id` match the device and run in progress, so a stale or mismatched report can never be replayed against the wrong device.
- **Exceptions allowlist** (`automation/exceptions.yaml`) — lets you tell the diff engine "this line existing on the device is fine, don't flag it," so you don't get drowned in noise from vendor-default lines.
- **Section scoping** (`--sections`) and **audit-only mode** (`--audit-only`) let you limit the blast radius of any run.
- **Atomic report writes** — audit/remediation reports are written to a temp file and only renamed into place once complete, so a crash mid-write can't leave a corrupted report behind.

## 5. Supported Platforms

| Vendor / OS      | Transport for config push | Transport for config read |
|-------------------|---------------------------|----------------------------|
| Arista EOS        | NAPALM (eAPI)              | Scrapli                    |
| Cisco IOS (vIOS)  | Scrapli                    | Scrapli                    |
| Aruba AOS-CX       | Scrapli                    | Scrapli                    |

Managed configuration sections: `hostname`, `interfaces`, `vlans`, `ntp`, `snmp`, `ospf`, `management`, `security`, `static_routes`. (Note: Cisco IOS L3 routers don't support Layer 2 VLAN commands, so the Cisco `vlans.j2` template intentionally renders nothing.)

## 6. Project Structure

```
netbox/
  netbox.yaml              # Source of Truth — describes the intended lab
  netbox_schemas.py         # Pydantic validation models for NetBox objects
  netbox_services.py         # Sync logic: create/update objects idempotently
  main.py                    # Orchestrates the NetBox bootstrap
  config_context.yaml        # Example / reference config contexts
  postman/                   # Postman collection + environment for manual API testing

automation/
  nornir_config.py           # Builds the Nornir inventory from NetBox
  builders.py                 # Turns NetBox data into validated DeviceConfig objects
  nornir_schemas.py            # Pydantic models for device configuration
  renderer.py                  # Jinja2 rendering engine, per-platform templates
  templates/{arista,cisco,aruba}/*.j2   # Per-vendor config templates
  getters/scrapli_getters.py    # Pulls running-config sections from devices
  diffing.py                     # Set-based diff engine + exceptions filtering
  exceptions.yaml                 # Allowlist of expected "unmanaged" lines
  senders/{napalm_senders,scrapli_senders}.py   # Push config to devices
  tasks.py                         # audit_task / remediate_task Nornir tasks
  main.py                           # CLI entry point / pipeline orchestrator
  reports/                           # Generated audit & remediation JSON reports

topology.clab.yaml           # Containerlab topology for the lab devices
test_config_context_rendering.py   # Unit tests for builders + renderer
requirements.txt
```

## 7. Technologies

- **NetBox** — network Source of Truth / DCIM-IPAM platform
- **Pynetbox** — Python client for the NetBox REST API
- **Nornir** — Python automation framework (inventory, task orchestration, concurrency)
- **NetBoxInventory2** — Nornir plugin that builds inventory straight from NetBox
- **Scrapli / nornir-scrapli** — screen-scraping transport for Cisco IOS & Aruba AOS-CX
- **NAPALM / nornir-napalm** — multi-vendor abstraction layer for Arista EOS
- **Jinja2** — templating engine for rendering vendor-specific configuration
- **Pydantic** — schema validation for both NetBox payloads and device configuration
- **Containerlab** — spins up the virtual lab topology (cEOS, vIOS, AOS-CX)
- **Postman** — manual/exploratory testing of the NetBox API
- **PyYAML / python-dotenv** — configuration and secrets loading

## 8. Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create a .env file in the project root
NB_URL=http://localhost:8000
NB_TOKEN=your_netbox_api_token
NETBOX_DEV_USER=your_device_ssh_username
NETBOX_DEV_PASS=your_device_ssh_password

# 3. Bring up the lab topology (requires Containerlab)
sudo containerlab deploy -t topology.clab.yaml

# 4. Bootstrap NetBox from netbox/netbox.yaml
python -m netbox.main
```

At this point NetBox is populated with the sites, devices, interfaces, IPs, cables, VLANs, and config contexts described in `netbox/netbox.yaml`, and the lab devices are reachable.

## 9. Usage

```bash
# Audit every device, report drift, do NOT touch any device
python -m automation.main --audit-only

# Audit + remediate in dry-run mode (default) — shows what WOULD change
python -m automation.main

# Audit + remediate for real
python -m automation.main --apply

# Target a single device
python -m automation.main --host ceos1 --apply

# Limit remediation to specific sections only
python -m automation.main --apply --sections ntp snmp
```

Each run prints a summary table like:

```
DEVICE       PLATFORM   DRIFT DETECTED   STATUS
ceos1        eos        True             SUCCESS
ceos2        eos        False            IN SYNC
vios1        ios        True             DRY RUN
```

## 10. How the Diff Engine Works

For each managed config section (e.g. `ntp`, `ospf`), the pipeline:

1. **Renders the intended config** for that section from NetBox data, using the device's platform-specific Jinja2 template.
2. **Retrieves the running config** for that same section directly from the device.
3. **Normalizes both** into sets of trimmed, non-empty lines.
4. **Computes the difference both ways:**
   - `missing` = lines that should be on the device but aren't → this is drift that remediation will push.
   - `unmanaged` = lines that are on the device but weren't expected → these are reported, but filtered against `exceptions.yaml` first, so known-safe lines (vendor defaults, banners, etc.) don't create noise.
5. A device is flagged as having drift if either list is non-empty after filtering.

This is intentionally a line-based, set-based diff rather than a full structural config parser — simple, fast, and easy to reason about, at the cost of being whitespace/line-order sensitive (which the normalization step accounts for).

## 11. Outputs & Audit Trail

Every run leaves a paper trail in `automation/reports/`:

- **`audit_<host>_<timestamp>_<run_id>.json`** — the full intended config, the running config's diff (missing/unmanaged lines per section), and whether drift was found.
- **`remediation_<host>_<timestamp>_<run_id>.json`** — which sections were pushed, whether each succeeded, the device's raw output, and whether the config was saved to startup config.

Because remediation reports carry the same `run_id` as the audit that triggered them, and because remediation refuses to run against a report for the wrong host or a stale `run_id`, you always have a verifiable, timestamped record of exactly what was found and exactly what was changed — useful both for troubleshooting and as a change-management audit trail.

## 12. Why This Project?

I built this to get real, hands-on experience with the pattern that shows up again and again in modern NetOps: **NetBox as Source of Truth → drift detection → automated remediation**, rather than treating network automation as "just push some config with a script." Specifically it let me practice:

- Designing an idempotent Source-of-Truth sync (NetBox bootstrap)
- Multi-vendor abstraction with Jinja2 + Pydantic validation
- Building a real audit/remediation loop instead of one-way config pushes
- Safe-by-default automation design (dry-run, report verification, exceptions allowlist)
- Testing infrastructure code (`test_config_context_rendering.py`)

## 13. Time Saved

In this 5-device lab, a full audit across all devices and all nine config sections runs in roughly 20 seconds. The manual equivalent — logging into each device one at a time, running `show running-config`, and comparing it line-by-line against notes or a spreadsheet — would realistically take 15–20 minutes, and is exactly the kind of check that gets skipped when things get busy. That gap only widens as the network grows: this pipeline scales by adding devices to NetBox, not by adding more manual checklist time.

## 14. Project Status

**Working end-to-end** in the lab environment described in `topology.clab.yaml`:

- NetBox bootstrap: ✅ sites, manufacturers, roles, device types, devices, interfaces, IP addresses, cables, VLANs, config contexts
- Audit pipeline: ✅ multi-vendor (EOS, IOS, AOS-CX), 9 config sections, drift reporting with exceptions filtering
- Remediation pipeline: ✅ dry-run and live modes, section targeting, report-integrity verification, config save
- Unit tests: ✅ builders + multi-platform template rendering (`test_config_context_rendering.py`)

## 15. Remaining Work

- Broaden test coverage to the diff engine, senders, and the NetBox sync layer (currently only builders/rendering are unit-tested)
- Add CI to run the test suite and lint on every change
- Support for additional platforms/vendors beyond EOS, IOS, and AOS-CX
- Structured/config-aware diffing (e.g. parsing into a config tree) instead of line-based diffing, to reduce false positives from harmless line-order differences
- Scheduling/orchestration (e.g. a cron job or pipeline trigger) for continuous, unattended auditing
- Alerting/notifications (Slack, email, etc.) when drift is detected, instead of relying on someone reading the JSON reports
- Expanding the NetBox Source of Truth to cover more object types (e.g. circuits, racks, power)
