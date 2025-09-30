# WSL网络桥接PowerShell配置脚本
# 需要在Windows PowerShell中以管理员身份运行

Write-Host "=== WSL网络桥接配置 ===" -ForegroundColor Green

# 1. 检查WSL状态
Write-Host "检查WSL状态..." -ForegroundColor Yellow
wsl --status

# 2. 获取WSL IP地址
Write-Host "获取WSL IP地址..." -ForegroundColor Yellow
$WSL_IP = (wsl hostname -I).Trim()
Write-Host "WSL IP: $WSL_IP" -ForegroundColor Cyan

# 3. 获取Windows主机IP
Write-Host "获取Windows主机IP..." -ForegroundColor Yellow
$WIN_IP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -like "192.168.*" -or $_.IPAddress -like "10.*" -or $_.IPAddress -like "172.*"} | Select-Object -First 1).IPAddress
Write-Host "Windows主机IP: $WIN_IP" -ForegroundColor Cyan

# 4. 测试网络连通性
Write-Host "测试网络连通性..." -ForegroundColor Yellow
Test-NetConnection -ComputerName $WSL_IP -Port 22

# 5. 配置Windows防火墙规则（如果需要）
Write-Host "配置Windows防火墙规则..." -ForegroundColor Yellow
New-NetFirewallRule -DisplayName "WSL UDP 30000" -Direction Inbound -Protocol UDP -LocalPort 30000 -Action Allow -ErrorAction SilentlyContinue

# 6. 显示网络适配器信息
Write-Host "网络适配器信息:" -ForegroundColor Yellow
Get-NetAdapter | Where-Object {$_.Status -eq "Up"} | Format-Table Name, InterfaceDescription, LinkSpeed

Write-Host "=== 配置完成 ===" -ForegroundColor Green
Write-Host "请重启WSL: wsl --shutdown" -ForegroundColor Red


