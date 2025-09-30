import socket
import json

# 广播内容
request = {
    "id": 1234564, # 随便
    "method": "Marstek.GetDevice",
    "params": {
        "ble_mac": "0"
    }
}
message = json.dumps(request).encode("utf-8")

# 创建 UDP 套接字
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

# 绑定本地IP和端口
sock.bind(("192.168.3.235", 30000))   # 这里本地端口也设为对应的 30000不改 ****ip改本机

# 发送广播到局域网
broadcast_addr = ("192.168.3.91", 30000)
print(f"发送广播到 {broadcast_addr} ...")
sock.sendto(message, broadcast_addr)

# 接收响应
sock.settimeout(5)  # 最多等5秒
try:
    while True:
        data, addr = sock.recvfrom(4096)
        if addr[0] == "192.168.3.235": # ****本机
            continue  # 忽略自己发出的广播
        print(f"\n收到来自 {addr} 的响应:")
        try:
            resp = json.loads(data.decode("utf-8"))
            print(json.dumps(resp, indent=4, ensure_ascii=False))
        except Exception:
            print(data.decode("utf-8", errors="ignore"))
except socket.timeout:
    print("\n没有收到更多设备响应 (超时退出)")
