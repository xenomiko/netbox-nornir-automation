import logging
import os
import sys
import traceback
from dotenv import load_dotenv
from scrapli import Scrapli

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("test_vios")

VIOS_IP = os.getenv("VIOS_IP", "172.20.20.2")
DEV_USER = os.getenv("NETBOX_DEV_USER", "admin")
DEV_PASS = os.getenv("NETBOX_DEV_PASS")

print("\n" + "=" * 60)
print("TEST 1: Direct Scrapli Connection (Outside Nornir)")
print("=" * 60)

scrapli_device = {
    "host": VIOS_IP,
    "auth_username": DEV_USER,
    "auth_password": DEV_PASS,
    "auth_secondary": DEV_PASS,
    "platform": "cisco_iosxe",
    "transport": "paramiko",
    "auth_strict_key": False,
    "ssh_config_file": False,
}

try:
    print(f"[*] Connecting directly to {VIOS_IP} as '{DEV_USER}' using Paramiko...")
    with Scrapli(**scrapli_device) as conn:
        print("[+] Direct SSH Connection Established!")
        res = conn.send_command("show running-config | include ^hostname")
        print(f"[+] Output: {res.result.strip()}")

except Exception as e:
    print("\n[-] Direct Scrapli Test Failed!")
    print(f"Exception Type: {type(e).__name__}")
    print(f"Exception Msg:  {e}")
    traceback.print_exc()

print("\n" + "=" * 60)
print("TEST 2: Nornir Execution & Inventory Inspection for vios1")
print("=" * 60)

try:
    from nornir import InitNornir
    from automation.getters.scrapli_getters import scrapli_getter

    # Initialize Nornir
    nr = InitNornir(config_file="config.yaml")

    # Filter for vios1 host
    vios_nr = nr.filter(name="vios1")

    if not vios_nr.inventory.hosts:
        print("[-] ERROR: Host 'vios1' was not found in Nornir inventory!")
    else:
        vios_host = vios_nr.inventory.hosts["vios1"]
        print(f"[*] Nornir Host Key:      {vios_host.name}")
        print(
            f"[*] Nornir Resolved Host: {vios_host.hostname}  <-- Must be an IP (e.g. {VIOS_IP}) or resolvable DNS"
        )
        print(f"[*] Nornir Username:      {vios_host.username}")
        print(
            f"[*] Nornir Password Set:  {'Yes' if vios_host.password else 'No (MISSING!)'}"
        )
        print(f"[*] Nornir Platform:      {vios_host.platform}")

        print("\n[*] Running 'scrapli_getter' task via Nornir on vios1...")
        result = vios_nr.run(
            task=scrapli_getter,
            section="hostname",
        )

        vios_res = result["vios1"]

        if vios_res.failed:
            print("\n[-] Nornir Task FAILED for vios1!")
            subtask_res = vios_res[0]
            print(f"[-] Result Payload: {subtask_res.result}")
            print(f"[-] Exception Object: {subtask_res.exception}")

            if subtask_res.exception:
                print("\n--- Full Exception Traceback ---")
                traceback.print_exception(
                    type(subtask_res.exception),
                    subtask_res.exception,
                    subtask_res.exception.__traceback__,
                )
        else:
            print("\n[+] Nornir Task SUCCEEDED for vios1!")
            print(f"[+] Result Output:\n{vios_res.result}")

except Exception as e:
    print("\n[-] Nornir Test Execution Exception:")
    print(f"Exception Type: {type(e).__name__}")
    print(f"Exception Msg:  {e}")
    traceback.print_exc()

print("\n" + "=" * 60)
