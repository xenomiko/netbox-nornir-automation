from types import SimpleNamespace
from automation.builders import (
    build_interface_config,
    build_vlan_config,
    intended_vlans_dict,
    build_ntp_config,
    build_snmp_config,
    build_ospf_config,
    build_management_config,
    build_security_config,
    build_device_config,
    build_from_context,
)
import pytest
from pydantic import ValidationError
from automation.nornir_schemas import (
    NtpConfig,
    VlanConfig,
    SecurityConfig,
    SnmpConfig,
    StaticRouteConfig,
    OspfConfig,
    DeviceConfig,
    ManagementConfig,
    InterfaceConfig,
)


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
    def __init__(self, interfaces=None, ips=None, vlans=None, device=None):
        self.interfaces = interfaces or []
        self.ips = ips or []
        self.vlans = vlans or []
        self.device = device
        self.dcim = SimpleNamespace(
            interfaces=SimpleNamespace(filter=lambda device_id: self.interfaces),
            devices=SimpleNamespace(get=lambda name: self.device),
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


# testing build_from_context


@pytest.mark.parametrize("key_input", ["", None, "wrong"])
def test_key_not_found_returns_none(key_input):
    config_context = {"ntp": {"enabled": True, "servers": ["10.0.0.1"]}}
    result = build_from_context(NtpConfig, config_context=config_context, key=key_input)
    assert result is None


def test_correct_key_returns_validated_model():
    config_context = {"ntp": {"enabled": True, "servers": ["10.0.0.1"]}}
    result = build_from_context(NtpConfig, config_context=config_context, key="ntp")
    assert isinstance(result, NtpConfig)
    assert result.enabled is True
    assert result.servers == ["10.0.0.1"]


@pytest.mark.parametrize("falsy_value", [None, {}])
def test_key_present_but_value_is_falsy_returns_none(falsy_value):
    config_context = {"ntp": falsy_value}
    result = build_from_context(NtpConfig, config_context=config_context, key="ntp")
    assert result is None


def test_invalid_data_with_valid_key(caplog):
    config_context = {"ntp": {"enabled": True, "servers": [123]}}
    result = build_from_context(NtpConfig, config_context=config_context, key="ntp")
    assert result is None
    assert "invalid 'ntp' config context data" in caplog.text


def test_missing_required_field_returns_none():
    config_context = {"ospf": {"enabled": True}}
    result = build_from_context(OspfConfig, config_context=config_context, key="ospf")
    assert result is None


def test_section_has_extra_field():
    config_context = {
        "ntp": {"enabled": True, "servers": ["10.0.0.1"], "testing": "test"}
    }
    result = build_from_context(NtpConfig, config_context=config_context, key="ntp")
    assert isinstance(result, NtpConfig)
    assert result.enabled is True
    assert result.servers == ["10.0.0.1"]


# testing intended_vlans_dict


def test_intended_vlans_dict_empty():
    nb = FakeNB(vlans=[])
    result = intended_vlans_dict(nb)
    assert result == {}


def test_intended_vlans_name_is_none():
    nb = FakeNB(vlans=[FakeVlan(name=None, vid=2)])
    result = intended_vlans_dict(nb)
    assert result[2] is None


def test_intended_vlans_one_vlan():
    nb = FakeNB(vlans=[FakeVlan(name="vlan1", vid=2)])
    result = intended_vlans_dict(nb)
    assert result[2] == "vlan1"


def test_intended_vlans_multiple_vlans():
    nb = FakeNB(vlans=[FakeVlan(name="vlan1", vid=2), FakeVlan(name="vlan2", vid=3)])
    result = intended_vlans_dict(nb)
    assert result[2] == "vlan1"
    assert result[3] == "vlan2"


def test_intended_vlans_vlan_ids_override():
    nb = FakeNB(vlans=[FakeVlan(name="vlan1", vid=2), FakeVlan(name="vlan2", vid=2)])
    result = intended_vlans_dict(nb)
    assert result[2] == "vlan2"


# testing wrapper builder functions


def test_build_snmp_config_wires_correct_model_and_key():
    config_context = {
        "snmp": {"enabled": True, "communities": ["public"], "servers": ["10.0.0.2"]}
    }
    result = build_snmp_config(config_context)
    assert isinstance(result, SnmpConfig)
    assert result.communities == ["public"]
    assert result.servers == ["10.0.0.2"]


def test_build_ospf_config_wires_correct_model_and_key():
    config_context = {
        "ospf": {"enabled": True, "process_id": 1, "networks": ["10.0.0.0/24"]}
    }
    result = build_ospf_config(config_context)
    assert isinstance(result, OspfConfig)
    assert result.process_id == 1
    assert result.networks == ["10.0.0.0/24"]


def test_build_management_config_wires_correct_model_and_key():
    config_context = {
        "management": {"management_interface": "mgmt0", "default_gateway": "10.0.0.1"}
    }
    result = build_management_config(config_context)
    assert isinstance(result, ManagementConfig)
    assert result.management_interface == "mgmt0"
    assert result.default_gateway == "10.0.0.1"


def test_build_security_config_wires_correct_model_and_key():
    config_context = {
        "security": {
            "ssh_enabled": True,
            "telnet_enabled": False,
            "password_encryption": True,
        }
    }
    result = build_security_config(config_context)
    assert isinstance(result, SecurityConfig)
    assert result.telnet_enabled is False


def test_build_ntp_config_wires_correct_model_and_key():
    config_context = {"ntp": {"enabled": True, "servers": ["10.0.0.1"]}}
    result = build_ntp_config(config_context)
    assert isinstance(result, NtpConfig)
    assert result.servers == ["10.0.0.1"]


# testing build_device_config


def test_build_device_config_minimal():
    device_obj = SimpleNamespace(id=1)
    nb = FakeNB(interfaces=[], ips=[], vlans=[], device=device_obj)
    task = SimpleNamespace(
        host=SimpleNamespace(
            name="router1",
            data={"config_context": {}},
        )
    )

    result = build_device_config(nb, task)

    assert isinstance(result, DeviceConfig)
    assert result.hostname == "router1"
    assert result.interfaces == []
    assert result.vlans == []
    assert result.ntp is None
    assert result.snmp is None
    assert result.ospf is None
    assert result.management is None
    assert result.security is None


def test_build_device_config_fully_populated():
    device_obj = SimpleNamespace(id=1)
    nb = FakeNB(
        interfaces=[FakeInterface(id=1, name="eth0", description="uplink")],
        ips=[FakeIP(assigned_object_id=1, address="192.168.1.1")],
        vlans=[FakeVlan(vid=10, name="data", status="active")],
        device=device_obj,
    )
    task = SimpleNamespace(
        host=SimpleNamespace(
            name="router1",
            data={
                "config_context": {
                    "ntp": {"enabled": True, "servers": ["10.0.0.1"]},
                    "snmp": {
                        "enabled": True,
                        "communities": ["public"],
                        "servers": ["10.0.0.2"],
                    },
                    "ospf": {
                        "enabled": True,
                        "process_id": 1,
                        "networks": ["10.0.0.0/24"],
                    },
                    "management": {
                        "management_interface": "mgmt0",
                        "default_gateway": "10.0.0.1",
                    },
                    "security": {
                        "ssh_enabled": True,
                        "telnet_enabled": False,
                        "password_encryption": True,
                    },
                }
            },
        )
    )

    result = build_device_config(nb, task)

    assert isinstance(result, DeviceConfig)
    assert result.hostname == "router1"

    assert len(result.interfaces) == 1
    assert result.interfaces[0].name == "eth0"
    assert result.interfaces[0].ip_addresses == ["192.168.1.1"]

    assert len(result.vlans) == 1
    assert result.vlans[0].name == "data"
    assert result.vlans[0].vlan_id == 10

    assert result.ntp.servers == ["10.0.0.1"]
    assert result.snmp.communities == ["public"]
    assert result.ospf.process_id == 1
    assert result.management.management_interface == "mgmt0"
    assert result.security.telnet_enabled is False


def test_build_device_config_uses_correct_device_lookup():
    device_obj = SimpleNamespace(id=99)
    nb = FakeNB(
        interfaces=[FakeInterface(id=99, name="eth5")],
        device=device_obj,
    )
    task = SimpleNamespace(
        host=SimpleNamespace(name="router2", data={"config_context": {}})
    )

    result = build_device_config(nb, task)

    assert len(result.interfaces) == 1
    assert result.interfaces[0].name == "eth5"
