import logging
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from .nornir_schemas import DeviceConfig
from pathlib import Path
import ipaddress

logger = logging.getLogger(__name__)

PLATFORM_TEMPLATE_DIR = {
    "eos": "arista",
    "ios": "cisco",
    "aoscx": "aruba",
}

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"
JINJA_ENV = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)


CONFIG_SECTIONS = [
    "hostname",
    "interfaces",
    "vlans",
    "ntp",
    "snmp",
    "ospf",
    "bgp",
    "management",
    "security",
    "static_routes",
]


def cidr_to_netmask(value: str) -> str:
    try:
        iface = ipaddress.ip_interface(value)
        return f"{iface.ip} {iface.netmask}"
    except ValueError:
        logger.error("Invalid IP/CIDR value for cidr_to_netmask: %r", value)
        raise


JINJA_ENV.filters["cidr_to_netmask"] = cidr_to_netmask


def render_section(section, device_config: DeviceConfig, platform) -> str:
    if platform not in PLATFORM_TEMPLATE_DIR:
        logger.error(
            "Unsupported platform '%s'. Supported options: %s",
            platform,
            list(PLATFORM_TEMPLATE_DIR),
        )
        raise ValueError(f"Invalid platform: {platform}")
    platform_dir = PLATFORM_TEMPLATE_DIR.get(platform)
    try:
        template = JINJA_ENV.get_template(f"{platform_dir}/{section}.j2")
        rendered = template.render(device=device_config)
    except TemplateNotFound as e:
        msg = (
            f"Template not found for platform='{platform}', "
            f"section='{section}': {e}"
        )
        logger.error(msg)
        raise
    logger.info(
        "Rendered section '%s' for platform '%s'.",
        section,
        platform,
    )
    return rendered


def render_sections(platform, device_config: DeviceConfig) -> dict[str, str]:
    rendered_sections = {}
    for section in CONFIG_SECTIONS:
        section_config = getattr(device_config, section, None)
        if section_config is None or section_config == "" or section_config == []:
            continue
        rendered_section = render_section(section, device_config, platform)
        rendered_sections[section] = rendered_section
    return rendered_sections
