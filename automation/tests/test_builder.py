from types import SimpleNamespace
from automation.builders import build_interface_config
import pytest
from pydantic import ValidationError


class FakeInterface:
    def __init__(self, id, name, description="", enabled=True, mgmt_only=False):
        self.id = id
        self.name = name
        self.description = description
        self.enabled = enabled
        self.mgmt_only = mgmt_only


class FakeIP:
    def __init__(self, assigned_object_id, address):
        self.assigned_object_id = assigned_object_id
        self.address = address


class FakeNB:
    def __init__(self, interfaces=None, ips=None):
        self.interfaces = interfaces or []
        self.ips = ips or []
        self.dcim = SimpleNamespace(
            interfaces=SimpleNamespace(filter=lambda device_id: self.interfaces)
        )
        self.ipam = SimpleNamespace(
            ip_addresses=SimpleNamespace(filter=lambda device_id: self.ips)
        )


def test_no_interfaces_returns_empty_list():
    nb = FakeNB(interfaces=[], ips=[])
    device = SimpleNamespace(id=1)
    result = build_interface_config(nb, device)
    assert result == []


def test_interface_with_no_ip():
    nb = FakeNB(
        interfaces=[FakeInterface(id=2, name="eth0")],
        ips=[],
    )
    device = SimpleNamespace(id=1)
    result = build_interface_config(nb, device)
    assert len(result) == 1
    assert result[0].name == "eth0"
    assert result[0].ip_addresses == []


def test_interface_with_one_ip():
    nb = FakeNB(
        interfaces=[FakeInterface(id=1, name="eth1")],
        ips=[FakeIP(assigned_object_id=1, address="192.168.1.1")],
    )
    device = SimpleNamespace(id=2)
    result = build_interface_config(nb, device)
    assert len(result) == 1
    assert result[0].name == "eth1"
    assert result[0].ip_addresses == ["192.168.1.1"]


def test_ip_with_assigned_object_id_none_is_skipped():
    nb = FakeNB(
        interfaces=[FakeInterface(id=1, name="eth1")],
        ips=[
            FakeIP(assigned_object_id=None, address="192.168.1.1"),
            FakeIP(assigned_object_id=1, address="192.168.1.2"),
        ],
    )
    device = SimpleNamespace(id=2)
    result = build_interface_config(nb, device)
    assert len(result) == 1
    assert result[0].name == "eth1"
    assert result[0].ip_addresses == ["192.168.1.2"]


def test_interface_with_multiple_ips():
    nb = FakeNB(
        interfaces=[FakeInterface(id=1, name="eth1")],
        ips=[
            FakeIP(assigned_object_id=1, address="192.168.1.1"),
            FakeIP(assigned_object_id=1, address="192.168.1.2"),
        ],
    )
    device = SimpleNamespace(id=2)
    result = build_interface_config(nb, device)
    assert len(result) == 1
    assert result[0].name == "eth1"
    assert result[0].ip_addresses == ["192.168.1.1", "192.168.1.2"]


def test_interface_and_ip_with_mismatching_id():
    nb = FakeNB(
        interfaces=[FakeInterface(id=1, name="eth1")],
        ips=[
            FakeIP(assigned_object_id=2, address="192.168.1.1"),
            FakeIP(assigned_object_id=1, address="192.168.1.2"),
        ],
    )
    device = SimpleNamespace(id=2)
    result = build_interface_config(nb, device)
    assert len(result) == 1
    assert result[0].name == "eth1"
    assert result[0].ip_addresses == ["192.168.1.2"]


def test_ip_with_address_None_is_skipped():
    nb = FakeNB(
        interfaces=[FakeInterface(id=1, name="eth1")],
        ips=[
            FakeIP(assigned_object_id=1, address=None),
            FakeIP(assigned_object_id=1, address="192.168.1.2"),
        ],
    )
    device = SimpleNamespace(id=2)
    result = build_interface_config(nb, device)
    assert len(result) == 1
    assert result[0].name == "eth1"
    assert result[0].ip_addresses == ["192.168.1.2"]


def test_description_is_empty():
    nb = FakeNB(
        interfaces=[FakeInterface(id=1, name="eth1", description="")],
        ips=[FakeIP(assigned_object_id=1, address="192.168.1.2")],
    )
    device = SimpleNamespace(id=1)
    result = build_interface_config(nb, device)
    assert len(result) == 1
    assert result[0].name == "eth1"
    assert result[0].description is None
    assert result[0].ip_addresses == ["192.168.1.2"]


def test_description_is_none():
    nb = FakeNB(
        interfaces=[FakeInterface(id=1, name="eth1", description=None)],
        ips=[FakeIP(assigned_object_id=1, address="192.168.1.2")],
    )
    device = SimpleNamespace(id=1)
    result = build_interface_config(nb, device)
    assert len(result) == 1
    assert result[0].name == "eth1"
    assert result[0].description is None
    assert result[0].ip_addresses == ["192.168.1.2"]


def test_description_is_string():
    nb = FakeNB(
        interfaces=[FakeInterface(id=1, name="eth1", description="first interface")],
        ips=[FakeIP(assigned_object_id=1, address="192.168.1.2")],
    )
    device = SimpleNamespace(id=1)
    result = build_interface_config(nb, device)
    assert len(result) == 1
    assert result[0].name == "eth1"
    assert result[0].description == "first interface"
    assert result[0].ip_addresses == ["192.168.1.2"]


def test_mgmt_only_true_and_false():
    nb = FakeNB(
        interfaces=[
            FakeInterface(id=1, name="eth1", mgmt_only=False),
            FakeInterface(id=2, name="eth2", mgmt_only=True),
        ],
        ips=[],
    )
    device = SimpleNamespace(id=3)
    result = build_interface_config(nb, device)
    assert result[0].mgmt_only is False
    assert result[1].mgmt_only is True
    assert result[0].name == "eth1"
    assert result[1].name == "eth2"


def test_enabled_true_and_false():
    nb = FakeNB(
        interfaces=[
            FakeInterface(id=1, name="eth1", enabled=False),
            FakeInterface(id=2, name="eth2", enabled=True),
        ],
        ips=[],
    )
    device = SimpleNamespace(id=3)
    result = build_interface_config(nb, device)
    assert result[0].enabled is False
    assert result[1].enabled is True
    assert result[0].name == "eth1"
    assert result[1].name == "eth2"


def test_name_is_empty_string():
    nb = FakeNB(
        interfaces=[FakeInterface(id=2, name="")],
        ips=[],
    )
    device = SimpleNamespace(id=2)
    with pytest.raises(ValidationError):
        build_interface_config(nb, device)


def test_multiple_interfaces_order():
    nb = FakeNB(
        interfaces=[
            FakeInterface(id=1, name="eth1"),
            FakeInterface(id=2, name="eth2"),
        ],
        ips=[],
    )
    device = SimpleNamespace(id=3)
    result = build_interface_config(nb, device)
    assert result[0].name == "eth1"
    assert result[1].name == "eth2"
