# Marstek 设备控制功能指南

## 🎯 **控制功能概述**

现在你的 Marstek 设备集成支持完整的充放电控制功能，包括：

### **1. 开关控制 (Switch)**
- **充电开关** - 开启/关闭充电功能
- **放电开关** - 开启/关闭放电功能  
- **自动模式开关** - 切换到自动运行模式

### **2. 数值控制 (Number)**
- **充电功率** - 设置充电功率 (0-2000W)
- **放电功率** - 设置放电功率 (0-2000W)
- **目标电量** - 设置目标电量 (0-100%)

### **3. 快捷操作 (Button)**
- **停止所有** - 立即停止所有充放电
- **最大充电** - 最大功率充电 (2000W)
- **最大放电** - 最大功率放电 (2000W)
- **紧急停止** - 切换到被动模式

## 📱 **用户控制界面**

### **方法1：在概览页面添加控制实体**

1. **进入 Home Assistant 概览页面**
2. **点击 ⋮ → 编辑仪表板**
3. **点击 + 添加卡片**
4. **选择 "实体"**
5. **搜索并添加以下实体**：

#### **开关控制**
- `switch.marstek_charge_enable_3`
- `switch.marstek_discharge_enable_3`
- `switch.marstek_auto_mode_3`

#### **数值控制**
- `number.marstek_charge_power_3`
- `number.marstek_discharge_power_3`
- `number.marstek_target_soc_3`

#### **快捷操作**
- `button.marstek_stop_all_3`
- `button.marstek_max_charge_3`
- `button.marstek_max_discharge_3`
- `button.marstek_emergency_stop_3`

### **方法2：使用控制面板配置**

复制 `control_panel_example.yaml` 中的配置到你的 Lovelace 编辑器中。

## 🔧 **控制操作说明**

### **充电控制**
1. **开启充电**：打开充电开关
2. **设置功率**：调整充电功率数值 (0-2000W)
3. **快捷充电**：点击"最大充电"按钮

### **放电控制**
1. **开启放电**：打开放电开关
2. **设置功率**：调整放电功率数值 (0-2000W)
3. **快捷放电**：点击"最大放电"按钮

### **自动模式**
1. **开启自动**：打开自动模式开关
2. **设置目标**：调整目标电量 (0-100%)
3. **设备将自动管理充放电**

### **紧急操作**
1. **停止所有**：立即停止当前充放电
2. **紧急停止**：切换到被动模式（完全停止）

## ⚠️ **安全注意事项**

### **功率设置**
- **充电功率**：设置为负值（系统自动处理）
- **放电功率**：设置为正值
- **最大功率**：不要超过设备额定功率

### **模式切换**
- **手动模式**：需要手动控制充放电
- **自动模式**：设备根据目标电量自动管理
- **被动模式**：设备完全停止，不进行充放电

### **操作建议**
1. **首次使用**：建议从小功率开始测试
2. **功率调整**：逐步调整功率，观察设备响应
3. **紧急情况**：使用紧急停止按钮
4. **定期检查**：监控设备状态和电池电量

## 🔄 **控制流程示例**

### **场景1：手动充电**
1. 打开充电开关
2. 设置充电功率为 1000W
3. 监控电池电量变化
4. 达到目标电量后关闭充电开关

### **场景2：自动管理**
1. 打开自动模式开关
2. 设置目标电量为 80%
3. 设备自动管理充放电
4. 监控设备运行状态

### **场景3：紧急停止**
1. 发现异常情况
2. 点击紧急停止按钮
3. 设备切换到被动模式
4. 检查设备状态

## 📊 **状态监控**

### **实时状态**
- **电池电量**：当前电池百分比
- **充放电功率**：当前功率值
- **运行模式**：Manual/Auto/Passive
- **充放电状态**：Charging/Selling/Idle

### **控制反馈**
- **开关状态**：显示当前开关状态
- **功率设置**：显示当前功率设置
- **操作日志**：记录所有控制操作

## 🚀 **高级功能**

### **自动化集成**
你可以使用 Home Assistant 的自动化功能：

```yaml
# 示例：低电量时自动充电
automation:
  - alias: "低电量自动充电"
    trigger:
      platform: numeric_state
      entity_id: sensor.marstek_battery_level_3
      below: 20
    action:
      - service: switch.turn_on
        entity_id: switch.marstek_charge_enable_3
      - service: number.set_value
        entity_id: number.marstek_charge_power_3
        value: 1500
```

### **脚本集成**
创建复杂的控制脚本：

```yaml
# 示例：智能充放电脚本
script:
  smart_charge_discharge:
    sequence:
      - service: switch.turn_on
        entity_id: switch.marstek_auto_mode_3
      - service: number.set_value
        entity_id: number.marstek_target_soc_3
        value: 85
```

现在你的 Marstek 设备集成具备了完整的控制功能！
