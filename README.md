# NetBox-Driven Network Configuration Automation

A Nornir-based automation framework that treats **NetBox as the single source of truth**, renders vendor-specific configuration from that data, pushes it to devices, and audits live devices against intent to catch drift.

## What it does

1. **Inventory** — Nornir pulls hosts straight from NetBox (`NetBoxInventory2`), using each device's primary IPv4 as the connection address.
2. **Build** — `builders.py` reads devices, interfaces, IPs, VLANs, and per-device NetBox config-context data (NTP, SNMP, OSPF, BGP, management, security) and validates it into strongly-typed Pydantic models (`nornir_schemas.py`).
3. **Render** — `renderer.py` maps each device's platform (`eos` / `ios` / `aoscx`) to a Jinja2 template set (`templates/arista`, `templates/cisco`, `templates/aruba`) and renders one config snippet per section (hostname, interfaces, vlans, ntp, snmp, ospf, bgp, management, security, static_routes).
4. **Push** — `senders/napalm_senders.py` sends the rendered config via NAPALM (`napalm_configure`), with `dry_run` supported for review-before-apply.
5. **Retrieve** — `getters/scrapli_getters.py` pulls the equivalent running-config sections back off the device via Scrapli, per-platform command maps.
6. **Diff** — `diffing.py` normalizes and compares intended vs. running config line-by-line, reporting `missing` (intended but absent) and `unmanaged` (present but not intended) lines, with a YAML-based exception list to suppress known/expected noise.

## Supported platforms

| NetBox platform slug | Vendor | Scrapli platform |
|---|---|---|
| `eos` | Arista | `arista_eos` |
| `ios` | Cisco | `cisco_iosxe` |
| `aoscx` | Aruba | `aruba_aoscx` |

## Lab topology

`topology.clab.yaml` spins up a Containerlab environment matching this: 3x Arista cEOS, 1x Cisco vIOS, 1x Aruba AOS-CX, wired together for end-to-end testing without touching production gear.

## Setup

```bash
pip install -r requirements.txt   # nornir, nornir-napalm, nornir-scrapli, nornir-netbox, pydantic, jinja2, pyyaml, python-dotenv

# .env
NB_URL=https://your-netbox-instance
NB_TOKEN=your-netbox-api-token
```

## Usage

```python
from automation.nornir_config import get_nornir
from automation.builders import build_device_config
from automation.renderer import render_sections

nr = get_nornir()

def task(task, nb):
    device_config = build_device_config(nb, task)
    rendered = render_sections(task.host.platform, device_config)
    # push with napalm_senders.push_vlan_config(task, config_text, dry_run=True)
    # audit with getters.get_running_config(task, sections) + diffing.diff_section(...)
```

## Why this exists

Manual, CLI-driven network changes don't scale and drift silently. This closes the loop: NetBox defines intent, automation enforces it, and the diff engine proves it's still true — repeatably, across vendors.

---

## Time estimates: this tool vs. other methods

Rough, per-device figures for a mid-size network (assume ~50 devices, mixed vendor). Actual numbers vary with environment size and operator experience — use these as a starting point, not a guarantee.

| Task | Manual CLI (per device) | Manual CLI (50 devices) | Template scripts, no source of truth (e.g. ad-hoc Python/Ansible with hardcoded vars) | This tool (NetBox-driven) |
|---|---|---|---|---|
| Push a single config change (e.g. new VLAN) | 5–10 min | 4–8 hrs | 1–2 min/device after script is written; ~1–2 hrs to write/validate script | Seconds/device once template exists; NetBox update + one run (~5–10 min total) |
| Onboard a new device (base config) | 20–40 min | N/A (one-off) | 10–15 min (fill in vars, run) | 2–5 min (add to NetBox, run pipeline) |
| Full config audit (drift detection) across fleet | 1–2 hrs (manual `show run` review) | 1–2 hrs | 20–30 min (script exists but comparison usually manual) | 5–10 min (automated getter + diff, exceptions pre-filtered) |
| Rolling out a new standard (e.g. NTP servers) fleet-wide | 5–10 min/device, 4–8 hrs total | 4–8 hrs | 30–60 min (update script + rerun) | 5 min (update NetBox config context, rerun) |
| Multi-vendor consistency (same intent, 3 platforms) | Manually re-derive per-vendor syntax each time, error-prone, 1–3 hrs | 1–3 hrs | Requires separate scripts/branches per vendor, 2–4 hrs to build | Native — one Pydantic model, per-platform Jinja2 template, same run |
| Post-change verification | 10–15 min manual comparison, per device | 8–12 hrs | Rarely automated; usually manual spot-check | Built into diff step, seconds/device |

**Takeaway:** the upfront cost is building the NetBox data model and templates; every change after that is a data update plus a single Nornir run instead of a per-device CLI session, and drift is provable rather than assumed.