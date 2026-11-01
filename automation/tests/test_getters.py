import pytest
from automation.getters.scrapli_getters import (
    AOSCX_SECTION_MATCHERS,
    COMMANDS,
    GETTERS,
    get_aoscx_running_config,
    get_hostname,
    get_interfaces,
    get_management,
    get_ntp,
    get_ospf,
    get_running_config,
    get_security,
    get_snmp,
    get_static_routes,
    get_vlans,
    scrapli_getter,
    _match_aoscx_section,
    ensure_scrapli_platform,
    send_command,
)
from automation.renderer import CONFIG_SECTIONS
from automation.getters import scrapli_getters
from scrapli.exceptions import ScrapliException

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


class FakeTask:
    def __init__(
        self,
        platform="eos",
        output="ntp server 10.10.10.10",
        exc=None,
        failed=False,
    ):
        self.host = SimpleNamespace(
            name="router1", platform=platform, connection_options={}
        )
        self.output = output
        self.exc = exc
        self.failed = failed
        self.calls = []

    def run(self, **kwargs):
        self.calls.append(kwargs)
        if self.exc:
            raise self.exc
        return [SimpleNamespace(result=self.output, failed=self.failed)]


class TestScrapliGetter:
    def test_happy_path(self):
        task = FakeTask(platform="eos", output="ntp server 10.0.0.1")
        res = scrapli_getter(task, "ntp")
        assert res.failed is False
        assert res.result == "ntp server 10.0.0.1"
        assert len(task.calls) == 1
        assert task.calls[0]["command"] == COMMANDS["eos"]["ntp"]
        assert task.calls[0]["task"] is send_command

    def test_generic_exception_returns_failed_result(self):
        task = FakeTask(exc=RuntimeError("runtime error"))
        res = scrapli_getter(task, "ntp")
        assert res.failed is True
        assert "Failed to retrieve ntp" in res.result
        assert "runtime error" in res.result

    def test_scrapli_exception_returns_failed_result(self):
        task = FakeTask(exc=ScrapliException("scrapli error"))
        res = scrapli_getter(task, "ntp")
        assert res.failed is True
        assert "Scrapli error while retrieving ntp" in res.result
        assert "scrapli error" in res.result

    def test_no_command_for_aoscx(self):
        task = FakeTask(platform="aoscx")
        res = scrapli_getter(task, "ntp")
        assert res.failed is True
        assert "No command defined" in res.result
        assert task.calls == []

    def test_no_command_for_unknown_section(self):
        task = FakeTask(platform="eos")
        res = scrapli_getter(task, "bgp")
        assert res.failed is True
        assert "No command defined" in res.result
        assert task.calls == []

    def test_value_error_branch(self, monkeypatch):
        def raiser(task):
            raise ValueError("bad platform")

        monkeypatch.setattr(scrapli_getters, "ensure_scrapli_platform", raiser)
        task = FakeTask(platform="eos")
        res = scrapli_getter(task, "ntp")
        assert res.failed is True
        assert "Cannot retrieve ntp" in res.result
        assert "bad platform" in res.result
        assert task.calls == []

    def test_failure_is_logged(self, caplog):
        task = FakeTask(exc=RuntimeError("boom"))
        scrapli_getter(task, "ntp")
        assert "router1" in caplog.text
        assert "boom" in caplog.text


class TestGetAoscxRunningConfig:
    def test_success_sends_full_config_and_parses(self):
        task = FakeTask(
            platform="aoscx",
            output="hostname sw1\nntp server 10.0.0.1",
        )
        result = get_aoscx_running_config(task, ["hostname", "ntp"])
        assert result == {
            "hostname": "hostname sw1",
            "ntp": "ntp server 10.0.0.1",
        }
        assert len(task.calls) == 1
        assert task.calls[0]["command"] == "show running-config"
        assert task.calls[0]["task"] is send_command

    def test_scrapli_exception_becomes_runtime_error(self):
        original = ScrapliException("boom")
        task = FakeTask(platform="aoscx", exc=original)
        with pytest.raises(RuntimeError) as exc_info:
            get_aoscx_running_config(task, ["ntp"])
        assert "Failed to retrieve running-config for aoscx" in str(exc_info.value)
        assert exc_info.value.__cause__ is original

    def test_failed_result_raises_runtime_error(self):
        task = FakeTask(platform="aoscx", output="device said no", failed=True)
        with pytest.raises(RuntimeError, match="device said no"):
            get_aoscx_running_config(task, ["ntp"])


class TestGetRunningConfig:
    def test_aoscx_delegates(self, monkeypatch):
        received = {}

        def fake_aoscx(task, sections):
            received["args"] = (task, sections)
            return {"ntp": "sentinel"}

        monkeypatch.setattr(scrapli_getters, "get_aoscx_running_config", fake_aoscx)
        task = FakeTask(platform="aoscx")
        result = get_running_config(task, ["ntp"])
        assert result == {"ntp": "sentinel"}
        assert received["args"] == (task, ["ntp"])

    def test_other_platforms_collect_each_section(self, monkeypatch):
        monkeypatch.setitem(
            GETTERS,
            "hostname",
            lambda task: SimpleNamespace(failed=False, result="hostname r1"),
        )
        monkeypatch.setitem(
            GETTERS,
            "ntp",
            lambda task: SimpleNamespace(failed=False, result="ntp server 1.1.1.1"),
        )
        result = get_running_config(FakeTask(platform="eos"), ["hostname", "ntp"])
        assert result == {
            "hostname": "hostname r1",
            "ntp": "ntp server 1.1.1.1",
        }

    def test_failed_getter_raises_and_stops(self, monkeypatch):
        later_calls = []

        def later(task):
            later_calls.append(task)
            return SimpleNamespace(failed=False, result="x")

        monkeypatch.setitem(
            GETTERS,
            "hostname",
            lambda task: SimpleNamespace(failed=True, result="nope"),
        )
        monkeypatch.setitem(GETTERS, "ntp", later)
        with pytest.raises(RuntimeError, match="hostname"):
            get_running_config(FakeTask(platform="eos"), ["hostname", "ntp"])
        assert later_calls == []

    def test_unknown_section_raises_value_error(self):
        with pytest.raises(ValueError, match="unknown section"):
            get_running_config(FakeTask(platform="eos"), ["bgp"])

    def test_unknown_section_is_detected_lazily(self, monkeypatch):
        calls = []

        def ntp(task):
            calls.append("ntp")
            return SimpleNamespace(failed=False, result="x")

        monkeypatch.setitem(GETTERS, "ntp", ntp)
        with pytest.raises(ValueError):
            get_running_config(FakeTask(platform="eos"), ["ntp", "bgp"])
        assert calls == ["ntp"]

    def test_empty_sections_returns_empty_dict(self):
        assert get_running_config(FakeTask(platform="eos"), []) == {}


@pytest.mark.parametrize(
    "wrapper, section",
    [
        (get_hostname, "hostname"),
        (get_interfaces, "interfaces"),
        (get_vlans, "vlans"),
        (get_ospf, "ospf"),
        (get_static_routes, "static_routes"),
        (get_management, "management"),
        (get_ntp, "ntp"),
        (get_snmp, "snmp"),
        (get_security, "security"),
    ],
)
def test_wrapper_passes_its_own_section(monkeypatch, wrapper, section):
    monkeypatch.setattr(scrapli_getters, "scrapli_getter", lambda task, sec: sec)
    assert wrapper(None) == section


def test_getters_cover_all_config_sections():
    assert set(GETTERS) == set(CONFIG_SECTIONS)


@pytest.mark.parametrize("platform", ["eos", "ios"])
def test_commands_cover_all_sections(platform):
    assert set(COMMANDS[platform]) == set(GETTERS)


def test_aoscx_matchers_cover_all_sections():
    assert set(AOSCX_SECTION_MATCHERS) == set(GETTERS)
