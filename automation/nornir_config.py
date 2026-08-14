import os
from dotenv import load_dotenv
from nornir import InitNornir

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
