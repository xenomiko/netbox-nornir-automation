import unittest
from unittest.mock import MagicMock
from automation.nornir_schemas import (
    DeviceConfig,
    NtpConfig,
    SnmpConfig,
    OspfConfig,
    BgpConfig,
    ManagementConfig,
    SecurityConfig,
    StaticRouteConfig,
)
from automation.builders import (
    build_ntp_config,
    build_snmp_config,
    build_ospf_config,
    build_bgp_config,
    build_management_config,
    build_security_config,
    build_static_routes_config,
    build_device_config,
)
from automation.renderer import render_sections, render_section


class TestConfigContext(unittest.TestCase):
    def setUp(self):
        self.sample_config_context = {
            "ntp": {"enabled": True, "servers": ["10.0.0.1", "10.0.0.2"]},
            "snmp": {
                "enabled": True,
                "communities": ["public"],
                "servers": ["10.0.0.10"],
            },
            "ospf": {
                "enabled": True,
                "process_id": 1,
                "router_id": "1.1.1.1",
                "networks": ["10.0.0.0/24 area 0"],
            },
            "bgp": {
                "enabled": True,
                "local_as": 65000,
                "router_id": "1.1.1.1",
                "neighbors": [{"address": "10.0.0.2", "remote_as": 65001, "description": "PEER1"}],
                "networks": ["10.0.0.0/24"],
            },
            "management": {
                "enabled": True,
                "management_interface": "Management1",
                "default_gateway": "10.0.0.254",
                "ssh_enabled": True,
            },
            "security": {
                "ssh_enabled": True,
                "telnet_enabled": False,
                "password_encryption": True,
            },
            "static_routes": [
                {"prefix": "192.168.100.0/24", "next_hop": "10.0.0.254"}
            ],
        }

    def test_builders_from_config_context(self):
        ctx = self.sample_config_context
        
        ntp = build_ntp_config(ctx)
        self.assertIsInstance(ntp, NtpConfig)
        self.assertEqual(ntp.servers, ["10.0.0.1", "10.0.0.2"])

        snmp = build_snmp_config(ctx)
        self.assertIsInstance(snmp, SnmpConfig)
        self.assertEqual(snmp.communities, ["public"])

        ospf = build_ospf_config(ctx)
        self.assertIsInstance(ospf, OspfConfig)
        self.assertEqual(ospf.process_id, 1)

        bgp = build_bgp_config(ctx)
        self.assertIsInstance(bgp, BgpConfig)
        self.assertEqual(bgp.local_as, 65000)

        mgmt = build_management_config(ctx)
        self.assertIsInstance(mgmt, ManagementConfig)
        self.assertEqual(mgmt.default_gateway, "10.0.0.254")

        sec = build_security_config(ctx)
        self.assertIsInstance(sec, SecurityConfig)
        self.assertTrue(sec.ssh_enabled)

        routes = build_static_routes_config(ctx)
        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0].prefix, "192.168.100.0/24")

    def test_render_sections_all_platforms(self):
        ctx = self.sample_config_context
        device_cfg = DeviceConfig(
            hostname="test-router",
            ntp=build_ntp_config(ctx),
            snmp=build_snmp_config(ctx),
            ospf=build_ospf_config(ctx),
            bgp=build_bgp_config(ctx),
            management=build_management_config(ctx),
            security=build_security_config(ctx),
            static_routes=build_static_routes_config(ctx),
        )

        for platform in ["eos", "ios", "aoscx"]:
            rendered = render_sections(platform, device_cfg)
            self.assertIn("hostname", rendered)
            self.assertIn("ntp", rendered)
            self.assertIn("10.0.0.1", rendered["ntp"])
            self.assertIn("snmp", rendered)
            self.assertIn("public", rendered["snmp"])
            self.assertIn("ospf", rendered)
            self.assertIn("bgp", rendered)
            self.assertIn("65000", rendered["bgp"])
            self.assertIn("static_routes", rendered)
            self.assertIn("192.168.100.0/24", rendered["static_routes"])


if __name__ == "__main__":
    unittest.main()
