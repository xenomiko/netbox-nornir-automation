# main.py
import logging
from dotenv import load_dotenv
from netbox_services import (
    get_netbox_client,
    load_device_data,
    sync_cable,
    sync_resources,
    build_name_cache,
    build_slug_cache,
)
from schemas import (
    ConfigContextCreate,
    DeviceTypeCreate,
    InterfaceCreate,
    IPAddressCreate,
    ManufacturerCreate,
    NetBoxDeviceCreate,
    PlatformCreate,
    RoleCreate,
    SiteCreate,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)


def main():
    load_dotenv()
    nb = get_netbox_client()
    data = load_device_data("netbox.yaml")

    sync_resources(nb.dcim.sites, data.get("sites", []), SiteCreate)
    sync_resources(
        nb.dcim.manufacturers, data.get("manufacturers", []), ManufacturerCreate
    )
    sync_resources(nb.dcim.device_roles, data.get("roles", []), RoleCreate)

    manufacturers_cache = build_slug_cache(nb.dcim.manufacturers)
    platforms_data = data.get("platforms", [])
    for p in platforms_data:
        if "manufacturer" in p and isinstance(p["manufacturer"], str):
            p["manufacturer"] = manufacturers_cache[p["manufacturer"]]

    sync_resources(nb.dcim.platforms, platforms_data, PlatformCreate)

    device_types_data = data.get("device_types", [])
    for dt in device_types_data:
        dt["manufacturer"] = manufacturers_cache[dt["manufacturer"]]

    sync_resources(
        nb.dcim.device_types,
        device_types_data,
        DeviceTypeCreate,
    )

    sites_cache = build_slug_cache(nb.dcim.sites)
    device_types_cache = build_slug_cache(nb.dcim.device_types)
    roles_cache = build_slug_cache(nb.dcim.device_roles)
    platforms_cache = build_slug_cache(nb.dcim.platforms)

    devices_data = data.get("devices", [])
    for dev in devices_data:
        dev["site"] = sites_cache[dev["site"]]
        dev["device_type"] = device_types_cache[dev["device_type"]]
        dev["role"] = roles_cache[dev["role"]]
        if dev.get("platform"):
            dev["platform"] = platforms_cache[dev["platform"]]

    sync_resources(
        nb.dcim.devices, devices_data, NetBoxDeviceCreate, lookup_field="name"
    )

    config_contexts_data = data.get("config_contexts", [])
    relation_endpoints = {
        "regions": nb.dcim.regions,
        "site_groups": nb.dcim.site_groups,
        "sites": nb.dcim.sites,
        "locations": nb.dcim.locations,
        "device_types": nb.dcim.device_types,
        "roles": nb.dcim.device_roles,
        "platforms": nb.dcim.platforms,
        "cluster_groups": nb.virtualization.cluster_groups,
        "clusters": nb.virtualization.clusters,
        "tenant_groups": nb.tenancy.tenant_groups,
        "tenants": nb.tenancy.tenants,
    }
    relation_caches = {
        field: build_slug_cache(endpoint)
        for field, endpoint in relation_endpoints.items()
    }
    for cc in config_contexts_data:
        for field in relation_endpoints:
            if field in cc and cc[field]:
                cc[field] = [relation_caches[field][slug] for slug in cc[field]]

    sync_resources(
        nb.extras.config_contexts,
        config_contexts_data,
        ConfigContextCreate,
        lookup_field="name",
    )

    devices_cache = build_name_cache(nb.dcim.devices)

    interfaces_data = data.get("interfaces", [])
    for iface in interfaces_data:
        iface["device"] = devices_cache[iface.pop("device_name")]

    sync_resources(
        nb.dcim.interfaces,
        interfaces_data,
        InterfaceCreate,
        lookup_field=[("device", "device_id"), "name"],
    )

    interfaces_cache = {(i.device.name, i.name): i.id for i in nb.dcim.interfaces.all()}

    ip_addresses_data = data.get("ip_addresses", [])
    primary_ips_by_device = {}
    for ip in ip_addresses_data:
        device_name = ip.pop("device_name", None)
        interface_name = ip.pop("interface_name", None)
        is_primary_ip4 = ip.pop("is_primary_ip4", False)
        is_primary_ip6 = ip.pop("is_primary_ip6", False)
        if device_name and interface_name:
            iface_id = interfaces_cache[(device_name, interface_name)]
            ip["assigned_object_type"] = "dcim.interface"
            ip["assigned_object_id"] = iface_id

            if is_primary_ip4:
                primary_ips_by_device.setdefault(device_name, {})["primary_ip4"] = ip[
                    "address"
                ]
            if is_primary_ip6:
                primary_ips_by_device.setdefault(device_name, {})["primary_ip6"] = ip[
                    "address"
                ]

    sync_resources(
        nb.ipam.ip_addresses,
        ip_addresses_data,
        IPAddressCreate,
        lookup_field="address",
    )

    if primary_ips_by_device:
        ip_addresses_cache = {ip.address: ip.id for ip in nb.ipam.ip_addresses.all()}
        for dev in devices_data:
            ip_fields = primary_ips_by_device.get(dev["name"])
            if not ip_fields:
                continue
            for field, address in ip_fields.items():
                dev[field] = ip_addresses_cache[address]

        sync_resources(
            nb.dcim.devices, devices_data, NetBoxDeviceCreate, lookup_field="name"
        )

    cables_data = data.get("cables", [])
    sync_cable(nb, cables_data)


if __name__ == "__main__":
    main()
