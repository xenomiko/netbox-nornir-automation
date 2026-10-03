import pytest
from automation.renderer import (
    cidr_to_netmask,
    cidr_to_ip,
    cidr_to_netmask_only,
    cidr_to_wildcard,
    render_section,
    JINJA_ENV,
    render_sections,
    CONFIG_SECTIONS,
)
from automation.nornir_schemas import (
    DeviceConfig,
    InterfaceConfig,
    NtpConfig,
    OspfConfig,
    SecurityConfig,
    SnmpConfig,
    ManagementConfig,
)

from jinja2 import DictLoader, TemplateNotFound


class TestCidrToNetmask:
    @pytest.mark.parametrize(
        "input_cidr, expected",
        [
            ("10.0.0.1/24", "10.0.0.1 255.255.255.0"),
            ("10.0.0.1/0", "10.0.0.1 0.0.0.0"),
            ("10.0.0.1/32", "10.0.0.1 255.255.255.255"),
            ("10.0.0.1", "10.0.0.1 255.255.255.255"),
            ("3fff:172:20:20::2/64", "3fff:172:20:20::2 ffff:ffff:ffff:ffff::"),
            (
                "3fff:172:20:20::2/128",
                "3fff:172:20:20::2 ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff",
            ),
            ("3fff:172:20:20::2/0", "3fff:172:20:20::2 ::"),
        ],
    )
    def test_valid_cidr_to_netmask(self, input_cidr, expected):
        assert cidr_to_netmask(input_cidr) == expected

    @pytest.mark.parametrize(
        "invalid_ip", ["10.10.10.1/44", "10.10.10/32", "10.10.10/33", "hello", None]
    )
    def test_invalid_ip_cidr(self, invalid_ip):
        with pytest.raises(ValueError):
            cidr_to_netmask(invalid_ip)


class TestCidrToIp:
    @pytest.mark.parametrize(
        "input_ip, output_ip",
        [
            ("10.10.10.10/24", "10.10.10.10"),
            ("10.10.10.10/32", "10.10.10.10"),
            ("10.10.10.10/0", "10.10.10.10"),
            ("3fff:172:20:20::2/64", "3fff:172:20:20::2"),
            ("3fff:172:20:20::2/128", "3fff:172:20:20::2"),
        ],
    )
    def test_valid_cidr_to_ip(self, input_ip, output_ip):
        assert cidr_to_ip(input_ip) == output_ip

    @pytest.mark.parametrize(
        "invalid_input, expected_output",
        [
            (None, "None"),
            ("", ""),
        ],
    )
    def test_no_slash_input_passes_through_unvalidated(
        self, invalid_input, expected_output
    ):
        assert cidr_to_ip(invalid_input) == expected_output

    @pytest.mark.parametrize(
        "invalid_input",
        [
            "/",
            "hello/32",
            "10.10.10/33",
        ],
    )
    def test_slash_present_but_malformed_raises(self, invalid_input):
        with pytest.raises(ValueError):
            cidr_to_ip(invalid_input)


class TestCidrToNetmaskOnly:
    @pytest.mark.parametrize(
        "input_cidr, expected",
        [
            ("10.0.0.1/24", "255.255.255.0"),
            ("10.0.0.1/0", "0.0.0.0"),
            ("10.0.0.1/32", "255.255.255.255"),
            ("10.0.0.1", "255.255.255.255"),
            ("10.0.0.5/24", "255.255.255.0"),
            ("3fff:172:20:20::2/64", "ffff:ffff:ffff:ffff::"),
        ],
    )
    def test_valid_cidr_to_netmask_only(self, input_cidr, expected):
        assert cidr_to_netmask_only(input_cidr) == expected

    def test_host_bits_are_ignored(self):
        assert cidr_to_netmask_only("10.0.0.5/24") == cidr_to_netmask_only(
            "10.0.0.0/24"
        )

    @pytest.mark.parametrize(
        "invalid_ip", ["10.10.10.1/44", "10.10.10/32", "10.10.10/33", "hello", None]
    )
    def test_invalid_ip_cidr(self, invalid_ip):
        with pytest.raises(ValueError):
            cidr_to_netmask_only(invalid_ip)


class TestCidrToWildcard:
    @pytest.mark.parametrize(
        "input_cidr, expected",
        [
            ("10.0.0.1/24", "0.0.0.255"),
            ("10.0.0.1/0", "255.255.255.255"),
            ("10.0.0.1/32", "0.0.0.0"),
            ("10.0.0.1", "0.0.0.0"),
            ("10.0.0.5/24", "0.0.0.255"),
            ("3fff:172:20:20::2/64", "::ffff:ffff:ffff:ffff"),
        ],
    )
    def test_valid_cidr_to_wildcard(self, input_cidr, expected):
        assert cidr_to_wildcard(input_cidr) == expected

    def test_host_bits_are_ignored(self):
        assert cidr_to_wildcard("10.0.0.5/24") == cidr_to_wildcard("10.0.0.0/24")

    @pytest.mark.parametrize(
        "invalid_ip", ["10.10.10.1/44", "10.10.10/32", "10.10.10/33", "hello", None]
    )
    def test_invalid_ip_cidr(self, invalid_ip):
        with pytest.raises(ValueError):
            cidr_to_wildcard(invalid_ip)


@pytest.fixture
def fake_templates(monkeypatch):
    def set_templates(mapping):
        monkeypatch.setattr(JINJA_ENV, "loader", DictLoader(mapping))

    return set_templates


class TestRenderSection:

    def test_hostname_renders(self, fake_templates):
        fake_templates({"arista/hostname.j2": "hostname {{ hostname }}"})
        device = DeviceConfig(hostname="ceos1")
        assert render_section("hostname", device, "eos") == "hostname ceos1"

    def test_unsupported_platform(self, fake_templates):
        fake_templates({"arista/hostname.j2": "hostname {{ hostname }}"})
        device = DeviceConfig(hostname="ceos1")
        with pytest.raises(ValueError):
            render_section("hostname", device, "sohaib")

    def test_device_prefix(self, fake_templates):
        fake_templates({"arista/hostname.j2": "hostname {{ device.hostname }}"})
        device = DeviceConfig(hostname="ceos1")
        assert render_section("hostname", device, "eos") == "hostname ceos1"

    def test_nested_list_field_correct_name(self, fake_templates):
        fake_templates(
            {
                "arista/interfaces.j2": "{% for i in interfaces %}{{ i.ip_addresses }}{% endfor %}"
            }
        )
        device = DeviceConfig(
            hostname="ceos1",
            interfaces=[
                InterfaceConfig(
                    name="Ethernet1", ip_addresses=["10.0.0.1/24", "10.0.0.2/24"]
                )
            ],
        )
        result = render_section("interfaces", device, "eos")
        assert result == "['10.0.0.1/24', '10.0.0.2/24']"

    def test_nested_list_field_wrong_name(self, fake_templates):
        fake_templates(
            {
                "arista/interfaces.j2": "{% for i in interfaces %}{{ i.ip_address }}{% endfor %}"
            }
        )
        device = DeviceConfig(
            hostname="ceos1",
            interfaces=[
                InterfaceConfig(
                    name="Ethernet1", ip_addresses=["10.0.0.1/24", "10.0.0.2/24"]
                )
            ],
        )
        result = render_section("interfaces", device, "eos")
        assert result == ""

    def test_empty_template(self, fake_templates):
        fake_templates({"arista/hostname.j2": ""})
        device = DeviceConfig(hostname="ceos1")
        result = render_section("hostname", device, "eos")
        assert result == ""

    def test_platform_lookup_is_case_sensitive(self, fake_templates):
        fake_templates({"arista/hostname.j2": "hostname {{ hostname }}"})
        device = DeviceConfig(hostname="ceos1")
        with pytest.raises(ValueError):
            render_section("hostname", device, "EOS")

    def test_missing_template(self, fake_templates):
        fake_templates({})
        device = DeviceConfig(hostname="ceos1")
        with pytest.raises(TemplateNotFound):
            render_section("hostname", device, "eos")


class TestRenderSections:
    @pytest.fixture
    def fake_render_section(self, monkeypatch):
        calls = []

        def _fake(section, device_config, platform):
            calls.append((section, platform))
            return f"rendered-{section}"

        monkeypatch.setattr("automation.renderer.render_section", _fake)
        return calls

    def test_skips_none_and_empty_sections(self, fake_render_section):
        device = DeviceConfig(hostname="ceos1")
        result = render_sections("eos", device)
        assert result == {"hostname": "rendered-hostname"}
        assert fake_render_section == [("hostname", "eos")]

    def test_populated_list_section(self, fake_render_section):
        device = DeviceConfig(
            hostname="ceos1",
            interfaces=[InterfaceConfig(name="Ethernet1")],
        )
        result = render_sections("eos", device)
        assert result == {
            "hostname": "rendered-hostname",
            "interfaces": "rendered-interfaces",
        }
        assert fake_render_section == [("hostname", "eos"), ("interfaces", "eos")]

    @pytest.mark.parametrize(
        "section, model",
        [
            ("ntp", NtpConfig()),
            ("snmp", SnmpConfig()),
            ("ospf", OspfConfig(process_id=1)),
            ("management", ManagementConfig()),
            ("security", SecurityConfig()),
        ],
    )
    def test_none_capable_sections(self, fake_render_section, section, model):
        device = DeviceConfig(hostname="ceos1", **{section: model})

        result = render_sections("eos", device)
        assert result == {
            "hostname": "rendered-hostname",
            section: f"rendered-{section}",
        }
        assert fake_render_section == [("hostname", "eos"), (section, "eos")]

    def test_false_looking_data(self, fake_render_section):
        device = DeviceConfig(
            hostname="ceos1", ntp=NtpConfig(enabled=False, servers=[])
        )
        result = render_sections("eos", device)
        assert result == {"hostname": "rendered-hostname", "ntp": "rendered-ntp"}
        assert fake_render_section == [("hostname", "eos"), ("ntp", "eos")]

    @pytest.mark.parametrize("platform", ["eos", "ios", "aoscx"])
    def test_multiple_platforms(self, fake_render_section, platform):
        device = DeviceConfig(hostname="ceos1")
        result = render_sections(platform, device)
        assert result == {"hostname": "rendered-hostname"}
        assert fake_render_section == [("hostname", platform)]

    def test_missing_template_propagates(self, fake_templates):
        fake_templates({"arista/hostname.j2": "hostname {{ hostname }}"})
        device = DeviceConfig(
            hostname="ceos1",
            interfaces=[InterfaceConfig(name="Ethernet1")],
        )

        with pytest.raises(TemplateNotFound) as exc_info:
            render_sections("eos", device)

        assert "arista/interfaces.j2" in str(exc_info.value)

    def test_result_follows_config_sections_order(self, fake_render_section):
        device = DeviceConfig(
            hostname="ceos1",
            interfaces=[InterfaceConfig(name="Ethernet1")],
            ntp=NtpConfig(),
            security=SecurityConfig(),
        )
        result = render_sections("eos", device)

        expected = [s for s in CONFIG_SECTIONS if s in result]
        assert list(result) == expected
        assert list(result) == ["hostname", "interfaces", "ntp", "security"]
        assert [section for section, _ in fake_render_section] == list(result)
