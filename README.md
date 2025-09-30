# Marstek 设备集成

Home Assistant 自定义集成，用于控制 Marstek VenusC/E 系列储能设备。

## 功能特性

- **设备发现**：自动发现局域网内的 Marstek 设备
- **数据监控**：实时监控电池电量、功率、运行模式等状态
- **自动化控制**：支持通过自动化进行充电、放电、停止操作
- **多设备支持**：同时管理多台设备，每台设备独立显示

## 目录结构

```
config/custom_components/marstek/
├── __init__.py              # 集成入口，注册服务和平台
├── config_flow.py           # 设备发现和配置流程
├── const.py                 # 常量定义（端口、超时等）
├── command_builder.py       # 设备命令构建器
├── udp_client.py            # UDP 通信客户端
├── sensor.py                # 传感器平台（数据监控）
├── device_action.py         # 设备动作（自动化控制）
├── services.yaml            # 服务定义文件
├── simple_card.yaml         # 仪表板卡片示例
└── README.md               # 本文档
```

## 核心文件说明

### 1. `__init__.py` - 集成入口
- **作用**：注册集成、平台和服务
- **关键功能**：
  - 创建全局 UDP 客户端
  - 注册三个自动化服务：`marstek.charge`、`marstek.discharge`、`marstek.stop`
  - 定义平台加载顺序

### 2. `sensor.py` - 传感器平台
- **作用**：提供设备状态监控
- **实体类型**：
  - `sensor.marstek_battery_level` - 电池电量（%）
  - `sensor.marstek_grid_power` - 电网功率（W）
  - `sensor.marstek_device_mode` - 运行模式
  - `sensor.marstek_battery_status` - 电池状态（充电/放电/空闲）
  - `sensor.marstek_device_ip` - 设备IP地址
  - `sensor.marstek_device_version` - 固件版本
- **轮询机制**：每10秒发送一次 `ES.GetMode` 请求获取设备状态

### 3. `device_action.py` - 设备动作
- **作用**：为自动化提供设备控制动作
- **动作类型**：
  - `charge` - 充电（-1300W，全天00:00-23:59）
  - `discharge` - 放电（1300W，全天00:00-23:59）
  - `stop` - 停止充放电（enable=0）
- **重试机制**：失败后自动重试5次，间隔2秒

### 4. `udp_client.py` - UDP 通信
- **作用**：处理与设备的 UDP 通信
- **关键功能**：
  - 绑定 `0.0.0.0:30000` 接收响应
  - 发送日志显示 `192.168.3.235:30000`
  - 请求-响应匹配机制
  - 超时处理（单次请求8秒超时）

### 5. `command_builder.py` - 命令构建
- **作用**：构建发送给设备的 JSON 命令
- **主要命令**：
  - `Marstek.GetDevice` - 设备发现
  - `ES.GetMode` - 获取设备状态
  - `ES.SetMode` - 设置设备模式

## 安装步骤

### 方法一：生产环境安装

#### 1. 复制文件
将整个 `marstek` 目录复制到 Home Assistant 的 `custom_components` 目录：
```bash
cp -r marstek /config/custom_components/
```

#### 2. 重启 Home Assistant
重启 HA 以加载新集成。

#### 3. 添加设备
1. 进入 **设置** → **设备与服务** → **集成**
2. 点击 **添加集成**，搜索 `Marstek`
3. 系统会自动发现局域网内的设备
4. 选择要添加的设备，完成配置

### 方法二：开发环境搭建

#### 1. 搭建开发环境
```bash
# 创建虚拟环境
python3.13 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
script/setup
```

#### 2. 运行 Home Assistant（开发模式）
```bash
# 停止现有 HA 进程（如果有）
pkill -f "hass -c config"

# 启动开发模式
hass -c config
```

#### 3. 添加集成
1. 在开发环境中，进入 **设置** → **设备与服务** → **集成**
2. 点击 **添加集成**，搜索 `Marstek`
3. 系统会自动发现局域网内的设备
4. 选择要添加的设备，完成配置

#### 4. 开发调试
- 修改代码后，在 HA 前端 **开发者工具** → **重新加载** → 选择对应平台重新加载
- 查看日志：`tail -f home-assistant.log`

## 自动化配置

### 方法一：设备动作（推荐）
1. 进入 **设置** → **自动化与场景** → **自动化**
2. 点击 **创建自动化**
3. 设置触发条件（如定时、传感器状态等）
4. 添加动作 → **选择设备** → 选择 Marstek 设备
5. 在动作列表中选择：
   - **充电** - 以1300W功率充电
   - **放电** - 以1300W功率放电  
   - **停止** - 停止充放电

### 方法二：调用服务
1. 在自动化动作中选择 **调用服务**
2. 服务选择：
   - `marstek.charge` - 充电
   - `marstek.discharge` - 放电
   - `marstek.stop` - 停止
3. 数据填写：
   ```yaml
   host: 192.168.3.91  # 设备IP
   power: 1300         # 功率（可选，charge/discharge时）
   ```

## 仪表板配置

### 使用示例卡片
复制 `simple_card.yaml` 内容到仪表板：
1. 进入 **概览** → 右上角三点 → **编辑仪表板**
2. 右上角三点 → **原始配置编辑器**
3. 粘贴 `simple_card.yaml` 内容
4. 替换实体ID为你的实际设备实体ID

### 实体ID查找
在 **设置** → **设备与服务** → **设备** → 选择 Marstek 设备，查看实体列表。

## 故障排除

### 1. 设备发现失败
- 检查设备与 HA 是否在同一网络
- 确认设备端口 30000 未被占用
- 查看 HA 日志中的 UDP 通信记录

### 2. 轮询超时
- 设备可能响应较慢，已优化为单次请求+2.5秒超时
- 如仍超时，可调整 `sensor.py` 中的 `SCAN_INTERVAL`（默认10秒）

### 3. 自动化动作失败
- 设备动作已内置重试机制（5次重试，间隔2秒）
- 检查设备IP是否正确
- 查看 HA 日志中的重试记录

### 4. 设备重复显示
- 确保每台设备使用不同的IP地址
- 删除重复的设备配置条目
- 重启 HA 清理缓存

## 开发说明

### 添加新的传感器
1. 在 `sensor.py` 中添加新的传感器类
2. 在 `MarstekDataUpdateCoordinator._async_update_data()` 中添加数据解析
3. 在 `async_setup_entry()` 中注册新传感器

### 添加新的设备动作
1. 在 `device_action.py` 中定义新的动作类型
2. 在 `async_get_actions()` 中添加动作
3. 在 `async_call_action_from_config()` 中实现动作逻辑

### 修改通信协议
1. 在 `command_builder.py` 中添加新命令
2. 在 `udp_client.py` 中处理新命令的响应
3. 更新相关平台的解析逻辑

## 版本历史

- **v1.0** - 基础功能实现
  - 设备发现和状态监控
  - 基础自动化控制
  - 多设备支持

- **v1.1** - 优化和修复
  - 统一设备标识为IP地址
  - 优化轮询机制，减少超时
  - 添加设备动作重试机制
  - 移除冗余的控制实体，简化UI

