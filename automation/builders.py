from .nornir_schemas import (
    InterfaceConfig,
    VlanConfig,
    NtpConfig,
    SnmpConfig,
    OspfConfig,
    BgpConfig,
    ManagementConfig,
    SecurityConfig,
    DeviceConfig,
)
import logging
from pydantic import ValidationError

logger = logging.getLogger(__name__)


def build_interface_config(nb, device) -> list[InterfaceConfig]:
    netbox_interfaces = list(nb.dcim.interfaces.filter(device_id=device.id))
    all_ips = nb.ipam.ip_addresses.filter(device_id=device.id)

    ips_by_interface = {}
    for ip in all_ips:
        if ip.assigned_object_id:
            ips_by_interface.setdefault(ip.assigned_object_id, []).append(ip.address)

    interfaces = []
    for interface in netbox_interfaces:
        interfaces.append(
            InterfaceConfig(
                name=interface.name,
                description=interface.description or None,
                enabled=interface.enabled,
                mgmt_only=interface.mgmt_only,
                ip_addresses=ips_by_interface.get(interface.id, []),
            )
        )

    return interfaces


def build_vlan_config(nb) -> list[VlanConfig]:
    netbox_vlans = list(nb.ipam.vlans.all())
    vlans = []
    for vlan in netbox_vlans:
        vlans.append(
            VlanConfig(
                vlan_id=vlan.vid,
                name=vlan.name or None,
                enabled=vlan.status == "active",
            )
        )

    return vlans


def build_from_context(model_class, config_context: dict, key: str):
    section = config_context.get(key)
    if not section:
        return None
    try:
        return model_class.model_validate(section)
    except ValidationError as err:
        logger.error(f"invalid '{key}' config context data: {err}")
        return None


def build_ntp_config(config_context: dict) -> NtpConfig | None:
    return build_from_context(NtpConfig, config_context, "ntp")


def build_snmp_config(config_context: dict) -> SnmpConfig | None:
    return build_from_context(SnmpConfig, config_context, "snmp")


def build_ospf_config(config_context: dict) -> OspfConfig | None:
    return build_from_context(OspfConfig, config_context, "ospf")


def build_bgp_config(config_context: dict) -> BgpConfig | None:
    return build_from_context(BgpConfig, config_context, "bgp")


def build_management_config(config_context: dict) -> ManagementConfig | None:
    return build_from_context(ManagementConfig, config_context, "management")


def build_security_config(config_context: dict) -> SecurityConfig | None:
    return build_from_context(SecurityConfig, config_context, "security")


def build_device_config(nb, task) -> DeviceConfig:
    device = nb.dcim.devices.get(name=task.host.name)
    config_context = task.host.data.get("config_context", {})

    return DeviceConfig(
        hostname=task.host.name,
        interfaces=build_interface_config(nb, device),
        vlans=build_vlan_config(nb),
        ntp=build_ntp_config(config_context),
        snmp=build_snmp_config(config_context),
        ospf=build_ospf_config(config_context),
        bgp=build_bgp_config(config_context),
        management=build_management_config(config_context),
        security=build_security_config(config_context),
    )
