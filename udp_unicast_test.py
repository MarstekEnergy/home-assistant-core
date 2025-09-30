#!/usr/bin/env python3
import asyncio
import json
import socket

LOCAL_IP = "192.168.3.235"
LOCAL_PORT = 30000
TARGETS = ["192.168.3.76", "192.168.3.91"]

async def recv(sock, timeout=5.0):
    sock.setblocking(False)
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while loop.time() < end:
        try:
            data, addr = sock.recvfrom(4096)
            return data, addr
        except BlockingIOError:
            await asyncio.sleep(0.05)
    return None, None

async def send_and_recv(sock, ip, port, msg, timeout=5.0):
    sock.sendto(msg.encode(), (ip, port))
    print(f"=> sent to {ip}:{port}: {msg}")
    data, addr = await recv(sock, timeout)
    if data:
        try:
            js = json.loads(data.decode(errors='ignore'))
        except Exception:
            js = {"raw": data.decode(errors='ignore')}
        print(f"<= recv from {addr}: {json.dumps(js, ensure_ascii=False, indent=2)}")
    else:
        print(f"!! timeout waiting from {ip}:{port}")

async def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind((LOCAL_IP, LOCAL_PORT))
    print(f"bound on {LOCAL_IP}:{LOCAL_PORT}")

    try:
        es_status = json.dumps({"id": 1, "method": "ES.GetStatus", "params": {"id": 0}})
        es_mode = json.dumps({"id": 2, "method": "ES.GetMode", "params": {"id": 0}})
        bat_status = json.dumps({"id": 3, "method": "Bat.GetStatus", "params": {"id": 0}})
        discover = json.dumps({"id": "woshishabi", "method": "Marstek.GetDevice", "params": {"ble_mac": "0"}})

        for target in TARGETS:
            print(f"\n=== testing {target} ===")
            await send_and_recv(sock, target, 30000, discover, 5.0)
            await send_and_recv(sock, target, 30000, es_status, 5.0)
            await send_and_recv(sock, target, 30000, es_mode, 5.0)
            await send_and_recv(sock, target, 30000, bat_status, 5.0)
    finally:
        sock.close()

if __name__ == "__main__":
    asyncio.run(main())


