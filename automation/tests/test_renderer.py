import pytest
from automation.renderer import cidr_to_netmask, cidr_to_ip


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
