# Marstek 传感器显示类型说明

## 📊 **传感器分类**

### **数值型传感器（图形化显示）**
这些传感器有 `state_class = "measurement"` 和单位，会显示为图形化仪表：

1. **电池电量** (`sensor.marstek_battery_level_*`)
   - 类型：百分比传感器
   - 单位：%
   - 显示：圆形仪表盘
   - 范围：0-100%

2. **电网功率** (`sensor.marstek_battery_power_*`)
   - 类型：功率传感器
   - 单位：W
   - 显示：圆形仪表盘
   - 范围：0-2000W

### **文本型传感器（纯文本显示）**
这些传感器没有 `state_class` 和单位，会显示为纯文本：

1. **设备运行模式** (`sensor.marstek_device_mode`)
   - 类型：文本传感器
   - 显示：纯文本
   - 值：Manual, Auto, Passive, Unknown

2. **电池充放电状态** (`sensor.marstek_battery_status`)
   - 类型：文本传感器
   - 显示：纯文本
   - 值：Charging, Selling, Idle, Unknown

3. **设备IP地址** (`sensor.marstek_device_ip_*`)
   - 类型：文本传感器
   - 显示：纯文本
   - 值：192.168.3.91

4. **设备版本号** (`sensor.marstek_device_version_*`)
   - 类型：文本传感器
   - 显示：纯文本
   - 值：版本号字符串

## 🔧 **技术实现**

### **强制文本型显示**
为了确保非数值传感器显示为纯文本，我们在传感器类中设置了：

```python
# 强制设置为文本型传感器，不显示图形化卡片
self._attr_device_class = None
self._attr_state_class = None
```

### **传感器配置对比**

| 传感器类型 | device_class | state_class | unit_of_measurement | 显示方式 |
|-----------|-------------|-------------|-------------------|---------|
| 电池电量 | None | measurement | % | 图形化仪表 |
| 电网功率 | None | measurement | W | 图形化仪表 |
| 运行模式 | None | None | None | 纯文本 |
| 充放电状态 | None | None | None | 纯文本 |
| 设备IP | None | None | None | 纯文本 |
| 设备版本 | None | None | None | 纯文本 |

## 📱 **卡片配置示例**

```yaml
- type: vertical-stack
  title: "🔋 Marstek 设备"
  cards:
    # 数值型传感器 - 图形化显示
    - type: gauge
      entity: sensor.marstek_battery_level_3
      name: "电池电量"
    - type: gauge
      entity: sensor.marstek_battery_power_3
      name: "电网功率"
    
    # 文本型传感器 - 纯文本显示
    - type: entities
      title: "📱 设备信息"
      entities:
        - sensor.marstek_device_mode
        - sensor.marstek_battery_status
        - sensor.marstek_device_ip_3
        - sensor.marstek_device_version_3
```

## ✅ **修改完成**

现在所有传感器都会按照预期显示：
- **电量和功率**：图形化仪表盘
- **其他所有传感器**：纯文本显示

这样既保持了重要数据的可视化效果，又避免了不必要的图形化显示。
