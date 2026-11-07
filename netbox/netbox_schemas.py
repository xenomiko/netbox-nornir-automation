from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SLUG_PATTERN = r"^[-a-zA-Z0-9_]+$"


class NetBoxBaseSchema(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class NetBoxDeviceCreate(NetBoxBaseSchema):
    name: str = Field(min_length=1)
    device_type: int
    role: int
    site: int
    status: Literal[
        "active",
        "offline",
        "staged",
        "decommissioning",
        "failed",
        "inventory",
        "planned",
    ] = "active"
    tenant: int | None = None
    platform: int | None = None
    primary_ip4: int | None = None
    primary_ip6: int | None = None
    serial: str | None = Field(default=None, min_length=1)
    asset_tag: str | None = Field(default=None, min_length=1)
    rack: int | None = None
    position: float | None = None
    face: Literal["front", "rear"] | None = None
    location: int | None = None
    custom_fields: dict[str, Any] | None = None


class SiteCreate(NetBoxBaseSchema):
    name: str = Field(min_length=1)
    slug: str = Field(min_length=1, max_length=100, pattern=SLUG_PATTERN)
    status: (
        Literal["active", "planned", "staging", "decommissioning", "retired"] | None
    ) = None
    region: int | None = None
    group: int | None = None
    time_zone: str | None = Field(default=None, min_length=1)


class RoleCreate(NetBoxBaseSchema):
    name: str = Field(min_length=1)
    slug: str = Field(min_length=1, max_length=100, pattern=SLUG_PATTERN)
    config_template: int | None = None
    vm_role: bool | None = None


class ManufacturerCreate(NetBoxBaseSchema):
    name: str = Field(min_length=1)
    slug: str = Field(min_length=1, max_length=100, pattern=SLUG_PATTERN)


class DeviceTypeCreate(NetBoxBaseSchema):
    model: str = Field(min_length=1)
    slug: str = Field(min_length=1, max_length=100, pattern=SLUG_PATTERN)
    manufacturer: int
    part_number: str | None = Field(default=None, min_length=1)


class ConfigContextCreate(NetBoxBaseSchema):
    name: str = Field(min_length=1)
    weight: int = 100
    description: str | None = None
    is_active: bool = True
    data: dict[str, Any]
    regions: list[int] | None = None
    site_groups: list[int] | None = None
    sites: list[int] | None = None
    locations: list[int] | None = None
    device_types: list[int] | None = None
    roles: list[int] | None = None
    platforms: list[int] | None = None
    cluster_groups: list[int] | None = None
    clusters: list[int] | None = None
    tenant_groups: list[int] | None = None
    tenants: list[int] | None = None
    tags: list[str] | None = None


class InterfaceCreate(NetBoxBaseSchema):
    name: str = Field(min_length=1)
    device: int
    type: str = "1000base-t"
    enabled: bool | None = True
    mgmt_only: bool | None = None
    description: str | None = None


class IPAddressCreate(NetBoxBaseSchema):
    address: str = Field(min_length=1)
    status: Literal["active", "reserved", "deprecated", "dhcp", "slaac"] = "active"
    assigned_object_type: str | None = None
    assigned_object_id: int | None = None
    dns_name: str | None = None
    description: str | None = None
    tenant: int | None = None


class PlatformCreate(NetBoxBaseSchema):
    name: str = Field(min_length=1)
    slug: str = Field(min_length=1, max_length=100, pattern=SLUG_PATTERN)
    manufacturer: int | None = None
    napalm_driver: str | None = Field(default=None, min_length=1)
    napalm_args: dict[str, Any] | None = None
    description: str | None = None


class VlanCreate(NetBoxBaseSchema):
    vid: int = Field(ge=1, le=4094)
    name: str = Field(min_length=1)
    status: Literal[
        "active",
        "reserved",
        "deprecated",
    ] = "active"
