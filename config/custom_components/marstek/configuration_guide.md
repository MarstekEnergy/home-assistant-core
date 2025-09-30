# Marstek 设备配置指南

## 🎯 概览页面优化

### 问题说明
默认情况下，每个 Marstek 设备会创建 4 个传感器：
- 电池电量 (Battery Level)
- 电池功率 (Battery Power) 
- 设备IP (Device IP)
- 设备版本 (Device Version)

两个设备 = 8 个传感器，在概览页面会显得很混乱。

### 🔧 解决方案

#### 方案1：隐藏不必要的传感器
在 Home Assistant 中：
1. 进入 **配置** → **实体注册表**
2. 搜索 `marstek`
3. 对于不需要显示的传感器，点击 **禁用**

**建议隐藏的传感器**：
- `sensor.marstek_device_ip_*` (设备IP - 通常不需要显示)
- `sensor.marstek_device_version_*` (设备版本 - 通常不需要显示)

**保留的传感器**：
- `sensor.marstek_battery_level_*` (电池电量 - 重要)
- `sensor.marstek_battery_power_*` (电池功率 - 重要)

#### 方案2：使用自定义卡片
使用提供的卡片配置文件：
- `lovelace_cards.yaml` - 基础卡片配置
- `beautiful_cards.yaml` - 美观的卡片配置（需要 card_mod 插件）

**使用方法**：
1. 在 Lovelace 编辑器中添加 "手动卡片"
2. 选择 "YAML" 模式
3. 复制对应的配置内容

#### 方案3：创建专用视图
1. 在 Lovelace 中创建新视图：**Marstek 设备**
2. 只添加需要的传感器到这个视图
3. 在概览页面隐藏这些传感器

### 📱 推荐的显示方式

**概览页面**：只显示电池电量
```
设备1电量: 85%  |  设备2电量: 92%
```

**设备详情页面**：显示完整信息
```
设备1 (192.168.3.91)
├── 电池电量: 85%
├── 电池功率: 15W
├── 设备IP: 192.168.3.91
└── 设备版本: 155
```

### 🎨 美观卡片效果

使用 `beautiful_cards.yaml` 配置后，你会得到：
- 渐变背景的卡片
- 圆角设计
- 阴影效果
- 清晰的分组显示

### 🔄 传感器名称优化

现在传感器名称包含设备IP，更容易区分：
- `Marstek Battery Level (192.168.3.91)`
- `Marstek Battery Level (192.168.3.76)`
- `Marstek Battery Power (192.168.3.91)`
- `Marstek Battery Power (192.168.3.76)`
