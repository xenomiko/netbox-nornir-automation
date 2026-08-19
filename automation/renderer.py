import ipaddress
import logging
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from .nornir_schemas import DeviceConfig

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


def cidr_to_ip(value: str) -> str:
    try:
        if "/" in str(value):
            return str(ipaddress.ip_interface(value).ip)
        return str(value)
    except ValueError:
        logger.error("Invalid IP/CIDR value for cidr_to_ip: %r", value)
        raise


def cidr_to_netmask_only(value: str) -> str:
    try:
        return str(ipaddress.ip_network(value, strict=False).netmask)
    except ValueError:
        logger.error("Invalid IP/CIDR value for cidr_to_netmask_only: %r", value)
        raise


def cidr_to_wildcard(value: str) -> str:
    try:
        return str(ipaddress.ip_network(value, strict=False).hostmask)
    except ValueError:
        logger.error("Invalid IP/CIDR value for cidr_to_wildcard: %r", value)
        raise


JINJA_ENV.filters["cidr_to_netmask"] = cidr_to_netmask
JINJA_ENV.filters["cidr_to_ip"] = cidr_to_ip
JINJA_ENV.filters["cidr_to_netmask_only"] = cidr_to_netmask_only
JINJA_ENV.filters["cidr_to_wildcard"] = cidr_to_wildcard


def render_section(section: str, device_config: DeviceConfig, platform: str) -> str:
    if platform not in PLATFORM_TEMPLATE_DIR:
        logger.error(
            "Unsupported platform '%s'. Supported options: %s",
            platform,
            list(PLATFORM_TEMPLATE_DIR),
        )
        raise ValueError(f"Invalid platform: {platform}")
    platform_dir = PLATFORM_TEMPLATE_DIR.get(platform)
    if hasattr(device_config, "model_dump"):
        context = device_config.model_dump()
    elif hasattr(device_config, "dict"):
        context = device_config.dict()
    elif isinstance(device_config, dict):
        context = device_config.copy()
    else:
        context = {}

    context["device"] = device_config

    try:
        template = JINJA_ENV.get_template(f"{platform_dir}/{section}.j2")
        rendered = template.render(**context)
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


def render_sections(platform: str, device_config: DeviceConfig) -> dict[str, str]:
    rendered_sections = {}
    for section in CONFIG_SECTIONS:
        section_config = getattr(device_config, section, None)
        if section_config is None or section_config == "" or section_config == []:
            continue
        rendered_section = render_section(section, device_config, platform)
        rendered_sections[section] = rendered_section
    return rendered_sections
