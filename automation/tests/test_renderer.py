import pytest
from automation.renderer import cidr_to_netmask


class TestCidrToNetmask:
    def test_standard_ipv4_cidr(self):
        assert cidr_to_netmask("10.0.0.1/24") == "10.0.0.1 255.255.255.0"

    def test_cidr_is_zero(self):
        assert cidr_to_netmask("10.0.0.1/0") == "10.0.0.1 0.0.0.0"

    def test_cidr_is_32(self):
        assert cidr_to_netmask("10.0.0.1/32") == "10.0.0.1 255.255.255.255"

    def test_no_netmask(self):
        assert cidr_to_netmask("10.0.0.1") == "10.0.0.1 255.255.255.255"

    @pytest.mark.parametrize(
        "invalid_ip", ["10.10.10.1/44", "10.10.10/32", "10.10.10/33", 33]
    )
    def test_invalid_ip_cidr(self, invalid_ip):
        ipaddress = invalid_ip
        with pytest.raises(ValueError):
            cidr_to_netmask(ipaddress)
