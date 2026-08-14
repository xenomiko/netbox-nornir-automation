import os
from nornir import InitNornir
from dotenv import load_dotenv

load_dotenv()


def get_nornir():
    return InitNornir(
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
