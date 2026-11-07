"""Smoke tests for the real Jinja2 templates.

test_renderer.py swaps in fake templates, so a typo in an actual .j2 file would
pass CI. These tests render every section for every platform using the real
template files.
"""

import pytest

from automation.nornir_schemas import (
    DeviceConfig,
    InterfaceConfig,
    ManagementConfig,
    NtpConfig,
    OspfConfig,
    SecurityConfig,
    SnmpConfig,
    StaticRouteConfig,
    VlanConfig,
)
from automation.renderer import (
    CONFIG_SECTIONS,
    PLATFORM_TEMPLATE_DIR,
    TEMPLATE_DIR,
    render_section,
    render_sections,
)

PLATFORMS = list(PLATFORM_TEMPLATE_DIR)

# Sections that are intentionally empty for a platform (comment-only templates).
EXPECTED_EMPTY = {
    ("ios", "vlans"),
    ("eos", "management"),
    ("aoscx", "security"),
}

# Fragments that must appear in the rendered output.
EXPECTED = {
    "eos": {
        "hostname": ["hostname lab-r1"],
        "interfaces": [
            "interface Ethernet1",
            "description uplink",
            "no switchport",
            "ip address 10.0.0.1/24",
            "description OOB_Management",
            "ipv6 address 3fff:172:20:20::6/64",
        ],
        "vlans": [
            "vlan 10",
            "name USERS",
            "vlan 20",
            "name SERVERS",
            "state suspend",
        ],
        "ntp": [
            "ntp server 10.0.0.1",
            "ntp server 10.0.0.2",
        ],
        "snmp": [
            "snmp-server community public ro",
            "snmp-server host 10.0.0.10 version 2c public",
        ],
        "ospf": [
            "router ospf 1",
            "router-id 1.1.1.1",
            "network 172.20.20.0/24 area 0.0.0.0",
        ],
        "management": [],
        "security": [
            "management telnet",
        ],
        "static_routes": [
            "ip route 0.0.0.0/0 172.20.20.1",
            "ip route 10.100.0.0/16 172.20.20.1 10",
        ],
    },
    "ios": {
        "hostname": ["hostname lab-r1"],
        "interfaces": [
            "interface Ethernet1",
            "description uplink",
            "ip address 10.0.0.1 255.255.255.0",
            "description OOB_Management",
            "ipv6 address 3FFF:172:20:20::6/64",
        ],
        "vlans": [],
        "ntp": [
            "ntp server 10.0.0.1",
            "ntp server 10.0.0.2",
        ],
        "snmp": [
            "snmp-server community public RO",
            "snmp-server host 10.0.0.10 version 2c public",
        ],
        "ospf": [
            "router ospf 1",
            "router-id 1.1.1.1",
            "network 172.20.20.0 0.0.0.255 area 0",
        ],
        "management": [
            "ip default-gateway 172.20.20.1",
        ],
        "security": [
            "line vty 0 4",
            "transport input ssh telnet",
            "service password-encryption",
        ],
        "static_routes": [
            "ip route 0.0.0.0 0.0.0.0 172.20.20.1",
            "ip route 10.100.0.0 255.255.0.0 172.20.20.1 10",
        ],
    },
    "aoscx": {
        "hostname": ["hostname lab-r1"],
        "interfaces": [
            "interface Ethernet1",
            "description uplink",
            "routing",
            "ip address 10.0.0.1/24",
            "ipv6 address 3fff:172:20:20::6/64",
            "ip ospf 1 area 0.0.0.0",
            "no shutdown",
        ],
        "vlans": [
            "vlan 10",
            "name USERS",
            "vlan 20",
            "name SERVERS",
        ],
        "ntp": [
            "ntp server 10.0.0.1",
            "ntp server 10.0.0.2",
        ],
        "snmp": [
            "snmp-server community public",
            "snmp-server host 10.0.0.10 trap version v2c",
        ],
        "ospf": [
            "router ospf 1",
            "router-id 1.1.1.1",
            "area 0.0.0.0",
        ],
        "management": [
            "ssh server vrf mgmt",
            "ssh server vrf default",
        ],
        "security": [],
        "static_routes": [
            "ip route 0.0.0.0/0 172.20.20.1",
            "ip route 10.100.0.0/16 172.20.20.1",
        ],
    },
}

CASES = [(platform, section) for platform in PLATFORMS for section in CONFIG_SECTIONS]


@pytest.fixture(scope="module")
def device():
    # telnet_enabled=True so the eos/ios security templates render something.
    return DeviceConfig(
        hostname="lab-r1",
        interfaces=[
            InterfaceConfig(
                name="Ethernet1",
                description="uplink",
                ip_addresses=["10.0.0.1/24"],
            ),
            InterfaceConfig(
                name="Management0",
                mgmt_only=True,
                ip_addresses=["172.20.20.6/24", "3fff:172:20:20::6/64"],
            ),
        ],
        vlans=[
            VlanConfig(vlan_id=10, name="USERS"),
            VlanConfig(vlan_id=20, name="SERVERS", enabled=False),
        ],
        static_routes=[
            StaticRouteConfig(prefix="0.0.0.0/0", next_hop="172.20.20.1"),
            StaticRouteConfig(
                prefix="10.100.0.0/16",
                next_hop="172.20.20.1",
                administrative_distance=10,
            ),
        ],
        ospf=OspfConfig(
            process_id=1,
            router_id="1.1.1.1",
            networks=["172.20.20.0/24 area 0"],
        ),
        ntp=NtpConfig(servers=["10.0.0.1", "10.0.0.2"]),
        snmp=SnmpConfig(communities=["public"], servers=["10.0.0.10"]),
        management=ManagementConfig(default_gateway="172.20.20.1"),
        security=SecurityConfig(telnet_enabled=True),
    )


def test_expectations_cover_every_platform_and_section():
    assert set(EXPECTED) == set(PLATFORMS)
    for platform in PLATFORMS:
        assert set(EXPECTED[platform]) == set(CONFIG_SECTIONS)


def test_every_platform_has_a_template_for_every_section():
    missing = [
        f"{directory}/{section}.j2"
        for directory in PLATFORM_TEMPLATE_DIR.values()
        for section in CONFIG_SECTIONS
        if not (TEMPLATE_DIR / directory / f"{section}.j2").is_file()
    ]
    assert missing == []


@pytest.mark.parametrize("platform, section", CASES)
def test_section_renders_expected_content(device, platform, section):
    rendered = render_section(section, device, platform)

    assert "{{" not in rendered
    assert "{%" not in rendered

    if (platform, section) in EXPECTED_EMPTY:
        assert rendered.strip() == ""
    else:
        assert rendered.strip() != ""

    for fragment in EXPECTED[platform][section]:
        assert fragment in rendered


@pytest.mark.parametrize("platform", PLATFORMS)
def test_render_sections_returns_every_section_in_order(device, platform):
    assert list(render_sections(platform, device)) == CONFIG_SECTIONS
