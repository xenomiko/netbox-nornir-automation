import pytest
from automation.renderer import (
    cidr_to_netmask,
    cidr_to_ip,
    cidr_to_netmask_only,
    cidr_to_wildcard,
)
from automation.nornir_schemas import DeviceConfig


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
