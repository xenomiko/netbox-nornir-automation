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
        "interfaces": "show running-config | section ^interface",
        "vlans": "show running-config | section ^vlan",
        "bgp": "show running-config | section ^router bgp",
        "ospf": "show running-config | section ^router ospf",
        "static_routes": "show running-config | include ^ip route",
    },
    "ios": {
        "interfaces": "show running-config | section interface",
        "vlans": "show running-config | section vlan",
        "bgp": "show running-config | section router bgp",
        "ospf": "show running-config | section router ospf",
        "static_routes": "show running-config | include ^ip route",
    },
    "aoscx": {
        "interfaces": "show running-config interface",
        "vlans": "show running-config | include vlan",
        "bgp": "show running-config bgp",
        "ospf": "show running-config ospf",
        "static_routes": "show running-config | include ip route",
        "ntp": "show running-config | include ntp",
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
        if "scrapli" not in task.host.connection_options:
            task.host.connection_options["scrapli"] = ConnectionOptions(
                platform=scrapli_platform
            )
        else:
            task.host.connection_options["scrapli"].platform = scrapli_platform

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
