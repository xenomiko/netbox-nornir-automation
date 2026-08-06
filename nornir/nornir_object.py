import os
import urllib3
from dotenv import load_dotenv
from nornir import InitNornir
from nornir_netbox.plugins.inventory import NetBoxInventory2

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

nb_token = os.getenv("NB_TOKEN")
auth_header = (
    f"Bearer {nb_token}" if nb_token.startswith("nbt_") else f"Token {nb_token}"
)


def patched_get_resources(self, url, params=None):
    self.session.headers["Authorization"] = auth_header
    resources = []
    while url:
        r = self.session.get(url, params=params)
        r.raise_for_status()
        data = r.json()
        resources.extend(data["results"])
        url = data.get("next")
    return resources


NetBoxInventory2._get_resources = patched_get_resources

nr = InitNornir(
    inventory={
        "plugin": "NetBoxInventory2",
        "options": {
            "nb_url": os.getenv("NB_URL"),
            "nb_token": nb_token,
            "ssl_verify": False,
            "use_platform_slug": True,
        },
    }
)

print(f"Connected. {len(nr.inventory.hosts)} hosts loaded from NetBox:")
for name in nr.inventory.hosts:
    print(f" - {name}")
