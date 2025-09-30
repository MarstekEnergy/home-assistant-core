#!/bin/bash
# WSL端口转发脚本
# 将WSL的UDP 30000端口转发到Windows主机

echo "=== WSL端口转发配置 ==="

# 获取WSL IP
WSL_IP=$(hostname -I | awk '{print $1}')
echo "WSL IP: $WSL_IP"

# 获取Windows主机IP
WIN_IP=$(ip route show | grep default | awk '{print $3}')
echo "Windows主机IP: $WIN_IP"

# 创建端口转发规则
echo "创建端口转发规则..."
# 注意：这需要在Windows PowerShell中以管理员身份运行
echo "请在Windows PowerShell中运行以下命令："
echo "netsh interface portproxy add v4tov4 listenport=30000 listenaddress=0.0.0.0 connectport=30000 connectaddress=$WSL_IP"

# 显示当前端口转发规则
echo "当前端口转发规则："
echo "netsh interface portproxy show v4tov4"

echo "=== 配置完成 ==="


