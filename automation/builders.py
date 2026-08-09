from schemas import InterfaceConfig, VlanConfig


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


from schemas import VlanConfig


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
