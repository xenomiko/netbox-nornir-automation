import os
from dotenv import load_dotenv
from nornir import InitNornir
import pynetbox
from pynetbox import RequestError
import logging

logger = logging.getLogger(__name__)
load_dotenv()


def get_nornir():
    nr = InitNornir(
        runner={
            "plugin": "threaded",
            "options": {"num_workers": 10},
        },
        inventory={
            "plugin": "NetBoxInventory2",
            "options": {
                "nb_url": os.getenv("NB_URL"),
                "nb_token": os.getenv("NB_TOKEN"),
                "ssl_verify": True,
                "use_platform_slug": True,
            },
        },
    )

    for host in nr.inventory.hosts.values():
        primary_ip4 = host.data.get("primary_ip4")
        if primary_ip4:
            if isinstance(primary_ip4, dict):
                raw_address = primary_ip4.get("address", "")
            else:
                raw_address = str(primary_ip4)
            if raw_address:
                host.hostname = raw_address.split("/")[0]

    return nr


def get_netbox_client(validate_connection: bool = True) -> pynetbox.core.api.Api:
    NETBOX_TOKEN = os.getenv("NB_TOKEN")
    NETBOX_URL = os.getenv("NB_URL")
    if not NETBOX_TOKEN or not NETBOX_URL:
        error_msg = (
            "Missing required environment variables: NETBOX_URL and/or" " NETBOX_TOKEN"
        )
        logger.error(error_msg)
        raise ValueError(error_msg)
    nb = pynetbox.api(url=NETBOX_URL, token=NETBOX_TOKEN)
    if validate_connection:
        try:
            nb.status()
        except RequestError as e:
            error_msg = (
                f"Failed to connect or authenticate with NetBox at {NETBOX_URL}: {e}"
            )
            logger.error(error_msg)
            raise ConnectionError(error_msg) from e
    return nb
