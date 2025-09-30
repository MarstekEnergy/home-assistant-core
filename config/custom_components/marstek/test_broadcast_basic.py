#!/usr/bin/env python3
"""
Marstek广播测试脚本 - 基础版
基于用户提供的代码结构
"""

import socket
import json
import subprocess
import re

def get_local_ips():
    """获取本地IP地址列表"""
    ips = []
    try:
        # 使用ip命令获取IP地址
        result = subprocess.run(['ip', 'addr', 'show'], capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            for line in lines:
                # 匹配IPv4地址
                ip_match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)/', line)
                if ip_match:
                    ip = ip_match.group(1)
                    if not ip.startswith("127."):  # 排除回环地址
                        ips.append(ip)
    except Exception as e:
        print(f"获取本地IP失败: {e}")
    return ips

def test_broadcast():
    """执行广播测试 - 多网卡绑定，每个网卡都在30000端口广播并监听"""
    print("=" * 60)
    print("Marstek广播测试脚本 - 基础版")
    print("=" * 60)
    
    # 1. 显示网络接口信息
    print("\n📡 网络接口信息:")
    print("-" * 40)
    local_ips = get_local_ips()
    
    for i, ip in enumerate(local_ips, 1):
        print(f"{i}. {ip}")
        if ip.startswith("172.28."):
            print(f"   ⚠️  检测到WSL环境: {ip}")
    
    if not local_ips:
        print("❌ 没有找到可用的网络接口")
        return
    
    # 2. 创建广播请求
    request = {
        "id": 1234564,
        "method": "Marstek.GetDevice",
        "params": {
            "ble_mac": "0"
        }
    }
    message = json.dumps(request).encode("utf-8")
    
    print(f"\n📤 广播请求内容:")
    print("-" * 40)
    print(json.dumps(request, indent=2, ensure_ascii=False))
    
    total_responses = 0
    
    # 3. 针对每个网卡在30000端口分别绑定、广播、监听
    for bind_ip in local_ips:
        print(f"\n🔗 网卡绑定: {bind_ip}:30000")
        print(f"🔌 创建UDP套接字并绑定 {bind_ip}:30000 ...")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.bind((bind_ip, 30000))
        except OSError as e:
            print(f"   ❌ 绑定失败: {e}")
            try:
                sock.close()
            except Exception:
                pass
            continue
        
        # 监听+重发：10秒窗口内每2秒广播一次，收到响应则提前结束
        print(f"📡 监听响应 (10秒，间隔2秒重发) - 绑定 {bind_ip}:30000")
        iface_responses = 0
        broadcast_addr = ("255.255.255.255", 30000)
        import time
        start_ts = time.monotonic()
        deadline_ts = start_ts + 10.0
        next_send_ts = start_ts  # 立刻第一次发送
        try:
            while True:
                now = time.monotonic()
                # 到达发送时机：立即 + 每2秒
                if now >= next_send_ts:
                    try:
                        print(f"📤 广播: 本地 {bind_ip}:30000 -> 目标 {broadcast_addr[0]}:{broadcast_addr[1]}")
                        sock.sendto(message, broadcast_addr)
                    except Exception as e:
                        print(f"   ❌ 发送失败: {e}")
                        break
                    next_send_ts += 2.0

                # 计算本轮等待时间：不超过到下次发送和到deadline的间隔，且至少0.1秒，最多0.5秒
                wait_ts = min(max(0.0, next_send_ts - now), max(0.0, deadline_ts - now))
                if wait_ts < 0.1:
                    wait_ts = 0.1
                if wait_ts > 0.5:
                    wait_ts = 0.5
                sock.settimeout(wait_ts)

                # 尝试接收
                try:
                    data, addr = sock.recvfrom(4096)
                    if addr[0] in local_ips:
                        continue
                    iface_responses += 1
                    total_responses += 1
                    print(f"\n📥 [绑定 {bind_ip}] 收到第 {iface_responses} 个响应: {addr[0]}:{addr[1]}")
                    try:
                        resp = json.loads(data.decode("utf-8"))
                        print(json.dumps(resp, indent=4, ensure_ascii=False))
                    except Exception as e:
                        print(f"原始数据: {data.decode('utf-8', errors='ignore')} (解析错误: {e})")
                    break  # 收到任意响应即结束该网卡轮询
                except socket.timeout:
                    pass

                # 超时退出
                if now >= deadline_ts:
                    print(f"⏰ 绑定 {bind_ip} 监听超时，收到 {iface_responses} 个响应")
                    break
        finally:
            sock.close()
            print("🔌 套接字已关闭")
    
    # 4. 总结
    print(f"\n📊 测试总结:")
    print("-" * 40)
    print(f"本地IP数量: {len(local_ips)}")
    print(f"总收到响应数量: {total_responses}")
    if total_responses == 0:
        print(f"\n⚠️  没有收到任何响应，可能的原因:")
        print(f"   1. WSL网络隔离问题")
        print(f"   2. 设备不在同一网段")
        print(f"   3. 防火墙阻止UDP通信")
        print(f"   4. 设备未开启或未响应")
    
    print(f"\n" + "=" * 60)

if __name__ == "__main__":
    test_broadcast()
