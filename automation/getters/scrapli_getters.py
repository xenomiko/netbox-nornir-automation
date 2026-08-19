import logging
import re
from nornir.core.task import Result, Task
from nornir_scrapli.tasks import send_command
from scrapli.exceptions import ScrapliException
from nornir.core.inventory import ConnectionOptions
from nornir.core.task import Task

SCRAPLI_PLATFORM_MAP = {
    "eos": "arista_eos",
    "ios": "cisco_iosxe",
    "aoscx": "aruba_aoscx",
}


def ensure_scrapli_platform(task: Task) -> str:
    platform = task.host.platform
    scrapli_platform = SCRAPLI_PLATFORM_MAP.get(platform)
    if scrapli_platform is None:
        raise ValueError(f"Unsupported platform for scrapli: {platform!r}")

    if "scrapli" not in task.host.connection_options:
        task.host.connection_options["scrapli"] = ConnectionOptions(
            platform=scrapli_platform
        )
    else:
        task.host.connection_options["scrapli"].platform = scrapli_platform

    return scrapli_platform


logger = logging.getLogger(__name__)

COMMANDS = {
    "eos": {
        "hostname": "show running-config | section ^hostname",
        "interfaces": "show running-config | section ^interface",
        "vlans": "show running-config | section ^vlan",
        "ospf": "show running-config | section ^router ospf",
        "static_routes": "show running-config | section ^ip route",
        "management": "show running-config | section ^management",
        "ntp": "show running-config | section ^ntp",
        "snmp": "show running-config | section ^snmp",
        "security": "show running-config | section ^aaa|^username|^banner",
    },
    "ios": {
        "hostname": "show running-config | include ^hostname",
        "interfaces": "show running-config | section interface",
        "vlans": "show running-config | section vlan",
        "ospf": "show running-config | section router ospf",
        "static_routes": "show running-config | include ip route",
        "management": "show running-config | section line",
        "ntp": "show running-config | include ntp",
        "snmp": "show running-config | include snmp-server",
        "security": "show running-config | section aaa|username|banner",
    },
}

AOSCX_SECTION_MATCHERS: dict[str, list[str]] = {
    "hostname": [r"^hostname\s"],
    "interfaces": [r"^interface\s"],
    "vlans": [r"^vlan\s"],
    "ospf": [r"^router ospf\s"],
    "static_routes": [r"^ip route\s"],
    "management": [r"^ssh\s", r"^https-server\b"],
    "ntp": [r"^ntp\s"],
    "snmp": [r"^snmp-server\s"],
    "security": [r"^aaa\s", r"^user\s", r"^banner\s"],
}


def _match_aoscx_section(header_line: str) -> str | None:
    for section, patterns in AOSCX_SECTION_MATCHERS.items():
        for pattern in patterns:
            if re.match(pattern, header_line):
                return section
    return None


def parse_aoscx_sections(raw_config: str, sections: list[str]) -> dict[str, str]:

    blocks: dict[str, list[str]] = {section: [] for section in sections}
    current_section: str | None = None
    current_block_lines: list[str] = []

    def flush() -> None:
        if current_section and current_block_lines:
            blocks[current_section].append("\n".join(current_block_lines))

    for raw_line in raw_config.splitlines():
        if not raw_line.strip():
            continue
        is_child_line = raw_line[0] in (" ", "\t")
        if is_child_line:
            if current_section:
                current_block_lines.append(raw_line.rstrip())
            continue

        flush()
        current_block_lines = []
        matched = _match_aoscx_section(raw_line.strip())
        current_section = matched if matched in blocks else None
        if current_section:
            current_block_lines = [raw_line.rstrip()]

    flush()

    return {section: "\n".join(lines) for section, lines in blocks.items()}


def get_aoscx_running_config(task: Task, sections: list[str]) -> dict[str, str]:
    ensure_scrapli_platform(task)
    try:
        result = task.run(task=send_command, command="show running-config")
    except ScrapliException as e:
        raise RuntimeError(f"Failed to retrieve running-config for aoscx: {e}") from e

    if result[0].failed:
        raise RuntimeError(
            f"Failed to retrieve running-config for aoscx: {result[0].result}"
        )

    parsed = parse_aoscx_sections(result[0].result, sections)
    logger.info(
        "[%s] Retrieved and parsed aoscx running-config into %d section(s).",
        task.host.name,
        len(sections),
    )
    return parsed


def scrapli_getter(task: Task, section: str) -> Result:
    platform = task.host.platform
    command = COMMANDS.get(platform, {}).get(section)
    if command is None:
        msg = f"No command defined for section={section!r} platform={platform!r}"
        logger.error(f"[{task.host.name}] {msg}")
        return Result(host=task.host, failed=True, result=msg)
    try:
        ensure_scrapli_platform(task)
        result = task.run(
            task=send_command,
            command=command,
        )
        output = result[0].result
        logger.info(f"[{task.host.name}] Retrieved {section} configuration.")
        return Result(
            host=task.host,
            result=output,
        )
    except ValueError as e:
        msg = f"Cannot retrieve {section}: {e}"
        logger.error(f"[{task.host.name}] {msg}")
        return Result(host=task.host, failed=True, result=msg)
    except ScrapliException as e:
        msg = f"Scrapli error while retrieving {section}: {e}"
        logger.error(f"[{task.host.name}] {msg}")
        return Result(
            host=task.host,
            failed=True,
            result=msg,
        )
    except Exception as e:
        msg = f"Failed to retrieve {section}: {e}"
        logger.error(f"[{task.host.name}] {msg}")
        return Result(
            host=task.host,
            failed=True,
            result=msg,
        )


def get_hostname(task: Task) -> Result:
    return scrapli_getter(task, "hostname")


def get_interfaces(task: Task) -> Result:
    return scrapli_getter(task, "interfaces")


def get_vlans(task: Task) -> Result:
    return scrapli_getter(task, "vlans")


def get_ospf(task: Task) -> Result:
    return scrapli_getter(task, "ospf")


def get_static_routes(task: Task) -> Result:
    return scrapli_getter(task, "static_routes")


def get_management(task: Task) -> Result:
    return scrapli_getter(task, "management")


def get_ntp(task: Task) -> Result:
    return scrapli_getter(task, "ntp")


def get_snmp(task: Task) -> Result:
    return scrapli_getter(task, "snmp")


def get_security(task: Task) -> Result:
    return scrapli_getter(task, "security")


GETTERS = {
    "hostname": get_hostname,
    "interfaces": get_interfaces,
    "vlans": get_vlans,
    "ospf": get_ospf,
    "static_routes": get_static_routes,
    "management": get_management,
    "ntp": get_ntp,
    "snmp": get_snmp,
    "security": get_security,
}


def get_running_config(task: Task, sections: list[str]) -> dict[str, str]:
    if task.host.platform == "aoscx":
        return get_aoscx_running_config(task, sections)
    running_config = {}
    for section in sections:
        getter = GETTERS.get(section)
        if getter is None:
            raise ValueError(f"unknown section: {section}")
        result = getter(task)
        if result.failed:
            raise RuntimeError(f"Failed to retrieve {section}: {result.result}")
        running_config[section] = result.result
    return running_config
