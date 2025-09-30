"""网络诊断工具，帮助调试广播问题."""

import socket
import subprocess
import sys
from typing import List, Dict, Any

def get_network_info() -> Dict[str, Any]:
    """获取网络信息用于诊断."""
    info = {
        "interfaces": [],
        "routes": [],
        "arp_table": [],
    }
    
    try:
        # 获取网络接口信息
        import psutil
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
        print("psutil not available")
    
    try:
        # 获取路由表
        result = subprocess.run(['ip', 'route'], capture_output=True, text=True)
        if result.returncode == 0:
            info["routes"] = result.stdout.strip().split('\n')
    except:
        pass
    
    try:
        # 获取ARP表
        result = subprocess.run(['arp', '-a'], capture_output=True, text=True)
        if result.returncode == 0:
            info["arp_table"] = result.stdout.strip().split('\n')
    except:
        pass
    
    return info

def print_network_diagnostic():
    """打印网络诊断信息."""
    print("=== 网络诊断信息 ===")
    
    info = get_network_info()
    
    print("\n网络接口:")
    for interface in info["interfaces"]:
        print(f"  接口: {interface['name']}")
        for addr in interface["addresses"]:
            print(f"    IP: {addr['ip']}")
            print(f"    子网掩码: {addr['netmask']}")
            print(f"    广播地址: {addr['broadcast']}")
    
    print("\n路由表:")
    for route in info["routes"][:5]:  # 只显示前5条
        print(f"  {route}")
    
    print("\nARP表 (前10条):")
    for arp in info["arp_table"][:10]:
        print(f"  {arp}")

if __name__ == "__main__":
    print_network_diagnostic()
