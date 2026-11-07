
from pydantic import BaseModel, Field


class InterfaceConfig(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None
    enabled: bool = True
    mgmt_only: bool = False
    ip_addresses: list[str] = Field(default_factory=list)


class VlanConfig(BaseModel):
    vlan_id: int = Field(ge=1, le=4094)
    name: str | None = None
    enabled: bool = True


class StaticRouteConfig(BaseModel):
    prefix: str = Field(min_length=1)
    next_hop: str | None = None
    outgoing_interface: str | None = None
    administrative_distance: int | None = Field(default=None, ge=1)


class OspfConfig(BaseModel):
    enabled: bool = True
    process_id: int = Field(ge=1)
    router_id: str | None = None
    networks: list[str] = []


class NtpConfig(BaseModel):
    enabled: bool = True
    servers: list[str] = Field(default_factory=list)


class SnmpConfig(BaseModel):
    enabled: bool = True
    communities: list[str] = Field(default_factory=list)
    servers: list[str] = Field(default_factory=list)


class ManagementConfig(BaseModel):
    enabled: bool = True
    management_interface: str | None = None
    default_gateway: str | None = None
    ssh_enabled: bool = True


class SecurityConfig(BaseModel):
    ssh_enabled: bool = True
    telnet_enabled: bool = False
    password_encryption: bool = True


class DeviceConfig(BaseModel):
    hostname: str = Field(min_length=1)
    interfaces: list[InterfaceConfig] = Field(default_factory=list)
    vlans: list[VlanConfig] = Field(default_factory=list)
    static_routes: list[StaticRouteConfig] = Field(default_factory=list)
    ospf: OspfConfig | None = None
    ntp: NtpConfig | None = None
    snmp: SnmpConfig | None = None
    management: ManagementConfig | None = None
    security: SecurityConfig | None = None
