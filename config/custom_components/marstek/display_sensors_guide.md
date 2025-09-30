# Marstek 传感器显示指南

## 🎯 **在概览页面显示传感器**

### 方法1：使用 Lovelace 卡片（推荐）

#### 步骤1：进入 Lovelace 编辑器
1. 打开 Home Assistant
2. 点击右上角 **⋮** → **编辑仪表板**
3. 点击右上角 **⋮** → **原始配置编辑器**

#### 步骤2：添加卡片配置
在 `views` 下找到你的视图，在 `cards` 数组中添加以下配置：

```yaml
# 设备1 - 完整信息卡片
- type: vertical-stack
  title: "🔋 Marstek 设备 1 (192.168.3.91)"
  cards:
    - type: gauge
      entity: sensor.marstek_battery_level_192_168_3_91
      name: "电池电量"
      unit: "%"
      min: 0
      max: 100
      severity:
        green: 50
        yellow: 20
        red: 0
      needle: true
    - type: gauge
      entity: sensor.marstek_battery_power_192_168_3_91
      name: "电网功率"
      unit: "W"
      min: 0
      max: 2000
      needle: true
    - type: entities
      title: "📱 设备信息"
      entities:
        - sensor.marstek_device_mode_192_168_3_91
        - sensor.marstek_battery_status_192_168_3_91
        - sensor.marstek_device_ip_192_168_3_91
        - sensor.marstek_device_version_192_168_3_91
```

#### 步骤3：修改IP地址
如果你的设备IP不是 `192.168.3.91`，需要修改：
- 将 `192_168_3_91` 替换为你的实际IP
- 例如：`192.168.1.100` → `192_168_1_100`

### 方法2：直接添加传感器到概览

#### 步骤1：进入概览页面
1. 打开 Home Assistant
2. 进入 **概览** 页面

#### 步骤2：添加传感器
1. 点击右上角 **⋮** → **编辑仪表板**
2. 点击 **+ 添加卡片**
3. 选择 **实体**
4. 搜索并添加以下传感器：
   - `sensor.marstek_device_mode_192_168_3_91`
   - `sensor.marstek_battery_status_192_168_3_91`

### 方法3：创建专用视图

#### 步骤1：创建新视图
1. 进入 **配置** → **仪表板**
2. 点击 **+ 添加仪表板**
3. 选择 **新建仪表板**
4. 命名为 **Marstek 设备**

#### 步骤2：添加传感器
1. 点击 **+ 添加卡片**
2. 选择 **实体**
3. 添加所有 Marstek 传感器

## 🔍 **检查传感器是否存在**

### 步骤1：查看实体注册表
1. 进入 **配置** → **实体注册表**
2. 搜索 `marstek`
3. 查看是否有以下传感器：
   - `sensor.marstek_device_mode_*`
   - `sensor.marstek_battery_status_*`

### 步骤2：检查传感器状态
1. 进入 **开发者工具** → **状态**
2. 搜索 `marstek`
3. 查看传感器状态和值

## 🚨 **常见问题解决**

### 问题1：传感器不显示
**解决方案**：
1. 重启 Home Assistant
2. 检查传感器名称是否正确
3. 查看 Home Assistant 日志

### 问题2：传感器显示 "不可用"
**解决方案**：
1. 检查设备是否在线
2. 查看轮询日志
3. 确认网络连接正常

### 问题3：传感器名称不匹配
**解决方案**：
1. 查看 **配置** → **实体注册表**
2. 获取正确的传感器名称
3. 更新卡片配置

## 📱 **移动端显示**

所有传感器都支持移动端显示，会自动调整大小。

## 🔄 **更新传感器**

当添加新设备时：
1. 复制现有设备卡片配置
2. 修改IP地址和标题
3. 保存配置

## 🎨 **自定义显示**

### 修改传感器名称
在传感器配置中添加 `name` 属性：
```yaml
- entity: sensor.marstek_device_mode_192_168_3_91
  name: "运行模式"
```

### 修改图标
在传感器配置中添加 `icon` 属性：
```yaml
- entity: sensor.marstek_device_mode_192_168_3_91
  icon: "mdi:cog"
```

### 修改单位
在传感器配置中添加 `unit` 属性：
```yaml
- entity: sensor.marstek_battery_power_192_168_3_91
  unit: "W"
```
