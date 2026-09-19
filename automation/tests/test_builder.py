from types import SimpleNamespace
from automation.builders import build_interface_config, build_vlan_config
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


class FakeVlan:
    def __init__(self, vid, name="", status="active"):
        self.vid = vid
        self.name = name
        self.status = status


class FakeNB:
    def __init__(self, interfaces=None, ips=None, vlans=None):
        self.interfaces = interfaces or []
        self.ips = ips or []
        self.vlans = vlans or []
        self.dcim = SimpleNamespace(
            interfaces=SimpleNamespace(filter=lambda device_id: self.interfaces)
        )
        self.ipam = SimpleNamespace(
            ip_addresses=SimpleNamespace(filter=lambda device_id: self.ips),
            vlans=SimpleNamespace(all=lambda: self.vlans),
        )


# testing build_interface_config


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


@pytest.mark.parametrize(
    "input_description, expected_description",
    [
        ("", None),
        (None, None),
        ("first interface", "first interface"),
    ],
)
def test_description_passthrough(input_description, expected_description):
    nb = FakeNB(
        interfaces=[FakeInterface(id=1, name="eth1", description=input_description)],
        ips=[FakeIP(assigned_object_id=1, address="192.168.1.2")],
    )
    device = SimpleNamespace(id=1)
    result = build_interface_config(nb, device)
    assert result[0].description == expected_description
    assert result[0].name == "eth1"
    assert result[0].ip_addresses == ["192.168.1.2"]


@pytest.mark.parametrize("mgmt_only_value", [True, False])
def test_mgmt_only_passthrough(mgmt_only_value):
    nb = FakeNB(
        interfaces=[FakeInterface(id=1, name="eth1", mgmt_only=mgmt_only_value)],
        ips=[],
    )
    device = SimpleNamespace(id=1)
    result = build_interface_config(nb, device)
    assert result[0].mgmt_only is mgmt_only_value


@pytest.mark.parametrize("enabled_value", [True, False])
def test_enabled_passthrough(enabled_value):
    nb = FakeNB(
        interfaces=[FakeInterface(id=1, name="eth1", enabled=enabled_value)],
        ips=[],
    )
    device = SimpleNamespace(id=1)
    result = build_interface_config(nb, device)
    assert result[0].enabled is enabled_value


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


# testing build_vlan_config


def test_vlans_empty():
    nb = FakeNB(vlans=[])
    result = build_vlan_config(nb)
    assert result == []


@pytest.mark.parametrize(
    "input_name, expected_name",
    [
        ("", None),
        (None, None),
        ("engineering", "engineering"),
    ],
)
def test_vlan_name_passthrough(input_name, expected_name):
    nb = FakeNB(vlans=[FakeVlan(vid=1, name=input_name)])
    result = build_vlan_config(nb)
    assert result[0].name == expected_name


@pytest.mark.parametrize(
    "input_status, expected_enabled",
    [
        ("active", True),
        ("deprecated", False),
        ("planned", False),
    ],
)
def test_vlan_status_maps_to_enabled(input_status, expected_enabled):
    nb = FakeNB(vlans=[FakeVlan(vid=1, name="test", status=input_status)])
    result = build_vlan_config(nb)
    assert result[0].enabled is expected_enabled


@pytest.mark.parametrize("invalid_vid", [0, 4095])
def test_vlan_id_out_of_range_raises_validation_error(invalid_vid):
    nb = FakeNB(vlans=[FakeVlan(vid=invalid_vid, name="test")])
    with pytest.raises(ValidationError):
        build_vlan_config(nb)


@pytest.mark.parametrize("valid_vid", [1, 4094])
def test_vlan_id_at_boundaries_is_valid(valid_vid):
    nb = FakeNB(vlans=[FakeVlan(vid=valid_vid, name="test")])
    result = build_vlan_config(nb)
    assert result[0].vlan_id == valid_vid


def test_multiple_vlans_order():
    nb = FakeNB(
        vlans=[
            FakeVlan(vid=10, name="data"),
            FakeVlan(vid=20, name="voice"),
        ]
    )
    result = build_vlan_config(nb)
    assert result[0].name == "data"
    assert result[1].name == "voice"
