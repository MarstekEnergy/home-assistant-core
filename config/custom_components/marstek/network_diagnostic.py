"""Network diagnostic tool to help debug broadcast issues."""

import socket
import subprocess
from typing import Any

try:
    import psutil
except ImportError:
    psutil = None


def get_network_info() -> dict[str, Any]:
    """Get network information for diagnostics."""
    info = {
        "interfaces": [],
        "routes": [],
        "arp_table": [],
    }

    try:
        # Get network interface information
        if psutil is None:
            return info
        for interface, addrs in psutil.net_if_addrs().items():
            interface_info = {
                "name": interface,
                "addresses": []
            }

            for addr in addrs:
                if addr.family == socket.AF_INET:
                    interface_info["addresses"].append({
                        "ip": addr.address,
                        "netmask": addr.netmask,
                        "broadcast": addr.broadcast,
                    })

            if interface_info["addresses"]:
                info["interfaces"].append(interface_info)

    except ImportError:
        pass  # psutil not available

    try:
        # Get routing table
        result = subprocess.run(['ip', 'route'], check=False, capture_output=True, text=True)
        if result.returncode == 0:
            info["routes"] = result.stdout.strip().split('\n')
    except (OSError, subprocess.SubprocessError):
        pass

    try:
        # Get ARP table
        result = subprocess.run(['arp', '-a'], check=False, capture_output=True, text=True)
        if result.returncode == 0:
            info["arp_table"] = result.stdout.strip().split('\n')
    except (OSError, subprocess.SubprocessError):
        pass

    return info

def print_network_diagnostic():
    """Print network diagnostic information."""
    # Diagnostic tool - print statements are intentional for console output
    print("=== Network Diagnostic Information ===")  # noqa: T201

    info = get_network_info()

    print("\nNetwork Interfaces:")  # noqa: T201
    for interface in info["interfaces"]:
        print(f"  Interface: {interface['name']}")  # noqa: T201
        for addr in interface["addresses"]:
            print(f"    IP: {addr['ip']}")  # noqa: T201
            print(f"    Netmask: {addr['netmask']}")  # noqa: T201
            print(f"    Broadcast: {addr['broadcast']}")  # noqa: T201

    print("\nRouting Table:")  # noqa: T201
    for route in info["routes"][:5]:  # Show only first 5
        print(f"  {route}")  # noqa: T201

    print("\nARP Table (first 10):")  # noqa: T201
    for arp in info["arp_table"][:10]:
        print(f"  {arp}")  # noqa: T201

if __name__ == "__main__":
    print_network_diagnostic()
