import pytest
from automation.getters.scrapli_getters import _match_aoscx_section


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

    def test_https_server_word_boundary(self):
        assert _match_aoscx_section("https-server") == "management"
