from dotenv import load_dotenv
from netbox_services import get_netbox_client

load_dotenv()
nb = get_netbox_client()

iface = nb.dcim.interfaces.get(device=4, name="pynetbox-test", type="virtual")
print(iface.id)
