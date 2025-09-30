#!/bin/bash
# WSL网络桥接配置脚本

echo "=== WSL网络桥接配置 ==="

# 1. 检查WSL版本
echo "检查WSL版本..."
wsl --version

# 2. 获取WSL IP地址
echo "获取WSL IP地址..."
WSL_IP=$(hostname -I | awk '{print $1}')
echo "WSL IP: $WSL_IP"

# 3. 获取Windows主机IP
echo "获取Windows主机IP..."
WIN_IP=$(ip route show | grep default | awk '{print $3}')
echo "Windows主机IP: $WIN_IP"

# 4. 测试网络连通性
echo "测试网络连通性..."
ping -c 1 $WIN_IP

# 5. 显示网络接口信息
echo "网络接口信息:"
ip addr show

# 6. 显示路由表
echo "路由表:"
ip route show

echo "=== 配置完成 ==="
echo "请重启WSL以使配置生效: wsl --shutdown"


