from pydantic import BaseModel, Field
from typing import Optional


class InterfaceConfig(BaseModel):
    name: str = Field(min_length=1)
    description: Optional[str] = None
    enabled: bool = True
    mgmt_only: bool = False
    ip_addresses: list[str] = Field(default_factory=list)


class VlanConfig(BaseModel):
    vlan_id: int = Field(ge=1, le=4094)
    name: Optional[str] = None
    enabled: bool = True


class StaticRouteConfig(BaseModel):
    prefix: str = Field(min_length=1)
    next_hop: Optional[str] = None
    outgoing_interface: Optional[str] = None
    administrative_distance: Optional[int] = Field(default=None, ge=1)


class OspfConfig(BaseModel):
    enabled: bool = True
    process_id: int = Field(ge=1)
    router_id: Optional[str] = None
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
    management_interface: Optional[str] = None
    default_gateway: Optional[str] = None
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
    ospf: Optional[OspfConfig] = None
    ntp: Optional[NtpConfig] = None
    snmp: Optional[SnmpConfig] = None
    management: Optional[ManagementConfig] = None
    security: Optional[SecurityConfig] = None
