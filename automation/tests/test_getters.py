import pytest
from automation.getters.scrapli_getters import (
    _match_aoscx_section,
    parse_aoscx_sections,
    ensure_scrapli_platform,
)
from types import SimpleNamespace
from nornir.core.inventory import ConnectionOptions


class TestMatchAoscxSection:
    @pytest.mark.parametrize(
        "header_line, expected_section",
        [
            ("hostname core-switch", "hostname"),
            ("interface 1/1/1", "interfaces"),
            ("vlan 10", "vlans"),
            ("router ospf 1", "ospf"),
            ("ip route 0.0.0.0/0 192.168.1.1", "static_routes"),
            ("ssh client source-interface 1/1/1", "management"),
            ("https-server vrf default", "management"),
            ("ntp server 192.168.1.254", "ntp"),
            ("snmp-server community public ro", "snmp"),
            ("aaa authentication login default local", "security"),
            ("user admin group administrators", "security"),
            ("banner motd ^C", "security"),
        ],
    )
    def test_section_matches_header_line(self, header_line, expected_section):
        section = _match_aoscx_section(header_line)
        assert section == expected_section

    @pytest.mark.parametrize(
        "header_line",
        [
            "host core-switch",
            " interface",
            "vlan-10",
            "",
            "!ip route 0.0.0.0/0 192.168.1.1",
            "!ssh client source-interface 1/1/1",
            "ntp-server 192.168.1.254",
            "snmp server community public ro",
            "username admin",
            "https-servers-disabled",
        ],
    )
    def test_near_matching_headers_dont_match(self, header_line):
        section = _match_aoscx_section(header_line)
        assert section is None

    def test_case_sensitivity(self):
        header = "Vlan 10"
        section = _match_aoscx_section(header)
        assert section is None


from automation.getters.scrapli_getters import parse_aoscx_sections

SAMPLE_CONFIG = "\n".join(
    [
        "! Version 10.08.1021",
        "hostname Core-Switch-01",
        "vlan 10",
        "    name Management",
        "vlan 20",
        "    name Data",
        "interface 1/1/1",
        "    description Uplink to Router",
        "    no shutdown",
        "    no routing",
        "interface 1/1/2",
        "    description Access Port",
        "    no shutdown",
        "    vlan access 20",
        "router ospf 1",
        "    router-id 10.0.0.1",
        "    area 0.0.0.0",
        "ip route 0.0.0.0/0 192.168.1.1",
        "ntp server 192.168.1.254 iburst",
        "ssh server vrf default",
        "snmp-server community public ro",
        "aaa authentication login default local",
    ]
)

ALL_SECTIONS = [
    "hostname",
    "interfaces",
    "vlans",
    "ospf",
    "static_routes",
    "management",
    "ntp",
    "snmp",
    "security",
]


class TestParseAoscxSections:
    def test_happy_path(self):
        expected = {
            "hostname": "hostname Core-Switch-01",
            "interfaces": "\n".join(
                [
                    "interface 1/1/1",
                    "    description Uplink to Router",
                    "    no shutdown",
                    "    no routing",
                    "interface 1/1/2",
                    "    description Access Port",
                    "    no shutdown",
                    "    vlan access 20",
                ]
            ),
            "vlans": "\n".join(
                [
                    "vlan 10",
                    "    name Management",
                    "vlan 20",
                    "    name Data",
                ]
            ),
            "ospf": "\n".join(
                [
                    "router ospf 1",
                    "    router-id 10.0.0.1",
                    "    area 0.0.0.0",
                ]
            ),
            "static_routes": "ip route 0.0.0.0/0 192.168.1.1",
            "management": "ssh server vrf default",
            "ntp": "ntp server 192.168.1.254 iburst",
            "snmp": "snmp-server community public ro",
            "security": "aaa authentication login default local",
        }
        result = parse_aoscx_sections(SAMPLE_CONFIG, sections=ALL_SECTIONS)
        assert result == expected

    def test_single_section_subset(self):
        result = parse_aoscx_sections(SAMPLE_CONFIG, sections=["ntp"])
        assert result == {"ntp": "ntp server 192.168.1.254 iburst"}

    def test_multiple_blocks_joined_in_order(self):
        config = "\n".join(
            [
                "interface 1/1/1",
                "    no shutdown",
                "interface 1/1/2",
                "    shutdown",
            ]
        )
        result = parse_aoscx_sections(config, sections=["interfaces"])
        assert result == {
            "interfaces": "interface 1/1/1\n    no shutdown\n"
            "interface 1/1/2\n    shutdown"
        }

    def test_children_of_unrequested_header_do_not_leak(self):
        config = "\n".join(
            [
                "interface 1/1/1",
                "    description Uplink",
                "    no shutdown",
                "ntp server 192.168.1.254",
            ]
        )
        result = parse_aoscx_sections(config, sections=["ntp"])
        assert result == {"ntp": "ntp server 192.168.1.254"}

    def test_orphan_child_line_as_first_line_is_ignored(self):
        config = "\n".join(
            [
                "    orphan before any header",
                "hostname Core-Switch-01",
                "ntp server 192.168.1.254",
            ]
        )
        result = parse_aoscx_sections(config, sections=["hostname", "ntp"])
        assert result == {
            "hostname": "hostname Core-Switch-01",
            "ntp": "ntp server 192.168.1.254",
        }
        assert "orphan" not in str(result)

    def test_comment_line_ends_block(self):
        config = "\n".join(
            [
                "hostname Core-Switch-01",
                "    description main switch",
                "!",
                "    orphan line after comment",
                "ntp server 192.168.1.254",
            ]
        )
        result = parse_aoscx_sections(config, sections=["hostname", "ntp"])
        assert result == {
            "hostname": "hostname Core-Switch-01\n    description main switch",
            "ntp": "ntp server 192.168.1.254",
        }
        assert "orphan" not in str(result)

    def test_empty_and_blank_input(self):
        sections = ["hostname", "ntp"]
        expected = {"hostname": "", "ntp": ""}
        assert parse_aoscx_sections("", sections=sections) == expected
        assert parse_aoscx_sections("\n\n  \n", sections=sections) == expected

    def test_requested_section_absent_returns_empty_string(self):
        result = parse_aoscx_sections(
            "hostname Core-Switch-01", sections=["hostname", "ospf"]
        )
        assert result == {"hostname": "hostname Core-Switch-01", "ospf": ""}

    def test_unknown_section_name_returns_empty_string(self):
        result = parse_aoscx_sections("hostname Core-Switch-01", sections=["bgp"])
        assert result == {"bgp": ""}

    def test_crlf_and_trailing_whitespace_are_cleaned(self):
        config = "hostname Core-Switch-01   \r\nntp server 192.168.1.254   \r\n"
        result = parse_aoscx_sections(config, sections=["hostname", "ntp"])
        assert result == {
            "hostname": "hostname Core-Switch-01",
            "ntp": "ntp server 192.168.1.254",
        }

    def test_empty_sections_list_returns_empty_dict(self):
        result = parse_aoscx_sections("hostname Core-Switch-01", sections=[])
        assert result == {}


class TestEnsureScrapliPlatform:
    @pytest.mark.parametrize("bad_platform", ["EOS", "junos", None])
    def test_unsupported_platform_raises(self, bad_platform):
        task = SimpleNamespace(
            host=SimpleNamespace(
                name="r1", platform=bad_platform, connection_options={}
            )
        )
        with pytest.raises(ValueError):
            ensure_scrapli_platform(task)

    @pytest.mark.parametrize(
        "platform, expected_platform",
        [("eos", "arista_eos"), ("aoscx", "aruba_aoscx"), ("ios", "cisco_iosxe")],
    )
    def test_plaform_is_as_expected(self, platform, expected_platform):
        task = SimpleNamespace(
            host=SimpleNamespace(name="r1", platform=platform, connection_options={})
        )
        result = ensure_scrapli_platform(task)
        assert result == expected_platform

    def test_ensure_scrapli_platform_preserves_extras(self):
        existing_opts = ConnectionOptions(extras={"auth_strict_key": False})

        task = SimpleNamespace(
            host=SimpleNamespace(
                name="router1",
                platform="eos",
                connection_options={"scrapli": existing_opts},
            )
        )
        result = ensure_scrapli_platform(task)
        assert result == "arista_eos"
        assert task.host.connection_options["scrapli"].platform == "arista_eos"
        assert task.host.connection_options["scrapli"].extras == {
            "auth_strict_key": False
        }

    def test_preserves_extras(self):
        task = SimpleNamespace(
            host=SimpleNamespace(name="r1", platform="eos", connection_options={})
        )
        result = ensure_scrapli_platform(task)
        assert result == "arista_eos"
        assert task.host.connection_options["scrapli"].platform == "arista_eos"

    def test_overwrites_existing_platform(self):
        existing_opts = ConnectionOptions(platform="aoscx")

        task = SimpleNamespace(
            host=SimpleNamespace(
                name="router1",
                platform="eos",
                connection_options={"scrapli": existing_opts},
            )
        )
        result = ensure_scrapli_platform(task)
        assert result == "arista_eos"
        assert task.host.connection_options["scrapli"].platform == "arista_eos"

    def test_is_idempotent(self):
        task = SimpleNamespace(
            host=SimpleNamespace(
                name="router1",
                platform="eos",
                connection_options={},
            )
        )
        first = ensure_scrapli_platform(task)
        opts_after_first = task.host.connection_options["scrapli"]
        second = ensure_scrapli_platform(task)
        assert first == second
        assert task.host.connection_options["scrapli"] is opts_after_first
