import logging
from nornir.core.inventory import ConnectionOptions
from nornir.core.task import Result, Task
from nornir_scrapli.tasks import send_command
from scrapli.exceptions import ScrapliException

logger = logging.getLogger(__name__)

SCRAPLI_PLATFORM_MAP = {
    "eos": "arista_eos",
    "ios": "cisco_iosxe",
    "aoscx": "aruba_aoscx",
}

COMMANDS = {
    "eos": {
        "hostname": "show running-config | section ^hostname",
        "interfaces": "show running-config | section ^interface",
        "vlans": "show running-config | section ^vlan",
        "bgp": "show running-config | section ^router bgp",
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
        "bgp": "show running-config | section router bgp",
        "ospf": "show running-config | section router ospf",
        "static_routes": "show running-config | include ip route",
        "management": "show running-config | section line",
        "ntp": "show running-config | include ntp",
        "snmp": "show running-config | include snmp-server",
        "security": "show running-config | section aaa|username|banner",
    },
    "aoscx": {
        "hostname": "show running-config | include hostname",
        "interfaces": "show running-config | include interface",
        "vlans": "show running-config | include vlan",
        "bgp": "show running-config | include bgp",
        "ospf": "show running-config | include ospf",
        "static_routes": "show running-config | include route",
        "management": "show running-config | include ssh",
        "ntp": "show running-config | include ntp",
        "snmp": "show running-config | include snmp-server",
        "security": "show running-config | include user",
    },
}


def scrapli_getter(task: Task, section: str) -> Result:
    platform = task.host.platform
    scrapli_platform = SCRAPLI_PLATFORM_MAP.get(platform)
    command = COMMANDS.get(platform, {}).get(section)

    if scrapli_platform is None:
        msg = f"Unsupported platform: {platform!r}"
        logger.error(f"[{task.host.name}] {msg}")
        return Result(host=task.host, failed=True, result=msg)

    if command is None:
        msg = f"No command defined for section={section!r} platform={platform!r}"
        logger.error(f"[{task.host.name}] {msg}")
        return Result(host=task.host, failed=True, result=msg)

    try:
        # 1. Safely retrieve or create Scrapli ConnectionOptions
        if "scrapli" not in task.host.connection_options:
            task.host.connection_options["scrapli"] = ConnectionOptions(
                platform=scrapli_platform,
                extras={},
            )

        scrapli_opts = task.host.connection_options["scrapli"]
        scrapli_opts.platform = scrapli_platform

        if scrapli_opts.extras is None:
            scrapli_opts.extras = {}

        # 2. Force Paramiko transport (for legacy Cisco KEX) & enable password
        scrapli_opts.extras.update(
            {
                "transport": "paramiko",
                "auth_strict_key": False,
                "ssh_config_file": False,
                "auth_secondary": task.host.password,
            }
        )

        # 3. Execute command
        result = task.run(
            task=send_command,
            command=command,
        )

        if result[0].failed:
            err_msg = str(result[0].result)
            logger.error(f"[{task.host.name}] Command failed for {section}: {err_msg}")
            return Result(
                host=task.host,
                failed=True,
                result=err_msg,
            )

        output = result[0].result
        logger.info(f"[{task.host.name}] Retrieved {section} configuration.")
        return Result(
            host=task.host,
            result=output,
        )

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


def get_bgp(task: Task) -> Result:
    return scrapli_getter(task, "bgp")


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
    "bgp": get_bgp,
    "ospf": get_ospf,
    "static_routes": get_static_routes,
    "management": get_management,
    "ntp": get_ntp,
    "snmp": get_snmp,
    "security": get_security,
}


def get_running_confg(task: Task, sections: list[str]) -> dict[str, str]:
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
