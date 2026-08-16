import logging
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from .nornir_schemas import DeviceConfig

logger = logging.getLogger(__name__)

PLATFORM_TEMPLATE_DIR = {
    "eos": "arista",
    "ios": "cisco",
    "aoscx": "aruba",
}

JINJA_ENV = Environment(
    loader=FileSystemLoader("templates"),
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
]


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
