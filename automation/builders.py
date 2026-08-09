from schemas import InterfaceConfig


def build_interface_config(nb, device) -> list[InterfaceConfig]:
    netbox_interfaces = list(nb.dcim.interfaces.filter(device_id=device.id))

    # single call for ALL ip addresses on this device
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
