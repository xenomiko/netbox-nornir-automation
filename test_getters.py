import os
from dotenv import load_dotenv
from nornir.core.inventory import ConnectionOptions

from automation.nornir_config import get_nornir
from automation.getters.scrapli_getters import get_running_confg

# Load environment credentials
load_dotenv()

# Initialize Nornir
nr = get_nornir()

# Set runtime credentials
dev_user = os.getenv("NETBOX_DEV_USER")
dev_pass = os.getenv("NETBOX_DEV_PASS")

nr.inventory.defaults.username = dev_user
nr.inventory.defaults.password = dev_pass

# Configure Scrapli connection options globally
for host in nr.inventory.hosts.values():
    if "scrapli" not in host.connection_options:
        host.connection_options["scrapli"] = ConnectionOptions(extras={})

    host.connection_options["scrapli"].extras.update(
        {
            "auth_strict_key": False,
            "ssh_config_file": False,
            "transport": "paramiko",
            "auth_secondary": dev_pass,  # Supplies enable password for Cisco IOS
        }
    )


def main():
    sections_to_pull = [
        "hostname",
        "interfaces",
        "vlans",
        "static_routes",
        "security",
    ]

    print(f"\n==================================================")
    print(f" RETRIEVING RUNNING CONFIG FOR SECTIONS: {sections_to_pull}")
    print(f"==================================================")

    results = nr.run(task=get_running_confg, sections=sections_to_pull)

    for host_name, multi_result in results.items():
        print(f"\n" + "=" * 50)
        print(f" DEVICE: {host_name}")
        print("=" * 50)

        # Handle failed tasks safely without crashing
        if multi_result.failed or multi_result.result is None:
            print("  [X] TASK FAILED")
            print(f"      Error: {multi_result.exception or multi_result.result}")
            continue

        # Process returned configuration dictionary
        device_config_data = multi_result.result

        for section, config_output in device_config_data.items():
            print(f"\n--- [ Section: {section} ] ---")
            if config_output and config_output.strip():
                print(config_output.strip())
            else:
                print("(No configuration returned for this section)")


if __name__ == "__main__":
    main()
