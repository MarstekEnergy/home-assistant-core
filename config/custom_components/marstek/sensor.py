"""Sensor platform for Marstek devices."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DOMAIN
from .udp_client import MarstekUDPClient
from .command_builder import get_battery_status, get_es_status, get_es_mode

_LOGGER = logging.getLogger(__name__)

# 更新间隔
SCAN_INTERVAL = timedelta(seconds=10)


class MarstekDataUpdateCoordinator(DataUpdateCoordinator):
    """每个设备的独立数据更新协调器."""

    def __init__(self, hass: HomeAssistant, udp_client: MarstekUDPClient, device_ip: str) -> None:
        """Initialize the coordinator."""
        self.udp_client = udp_client
        self.device_ip = device_ip
        super().__init__(
            hass,
            _LOGGER,
            name=f"Marstek {device_ip}",
            update_interval=SCAN_INTERVAL,
        )
        _LOGGER.debug("设备 %s 轮询协调器已启动，轮询间隔: %s秒", device_ip, SCAN_INTERVAL.total_seconds())

    async def _async_update_data(self) -> dict[str, Any]:
        """使用单个 ES.GetStatus 请求获取所有数据."""
        _LOGGER.debug("开始轮询设备: %s", self.device_ip)
        _LOGGER.debug("UDP客户端: %s", self.udp_client)
        
        # 获取当前数据作为默认值（保留旧数据）
        current_data = self.data or {}
        result_data = {
            "battery_soc": current_data.get("battery_soc", 0),
            "battery_power": current_data.get("battery_power", 0),
            "device_mode": current_data.get("device_mode", "Unknown"),
            "battery_status": current_data.get("battery_status", "Unknown"),
            "device_ip": self.device_ip,
            "last_update": asyncio.get_event_loop().time(),
        }
        
        # 延迟函数
        def delay(ms):
            return asyncio.sleep(ms / 1000.0)
        
        # 单次 ES.GetMode（含 bat_soc 与 ongrid_power），避免一轮发送两次导致设备限流
        async def es_status_request():
            try:
                _LOGGER.debug("开始 ES.GetMode 查询到设备: %s", self.device_ip)
                mode_as_status_command = get_es_mode(0)
                _LOGGER.info("Sensor发送请求到 %s | %s", self.device_ip, mode_as_status_command)
                # 最多等待 2.5 秒
                mode_as_status_result = await self.udp_client.send_request(
                    mode_as_status_command, self.device_ip, self.udp_client._port, timeout=2.5
                )
                _LOGGER.info("Sensor收到响应自 %s | %s", self.device_ip, mode_as_status_result)

                status_data = mode_as_status_result.get("result", {})
                _LOGGER.debug("ES.GetMode 原始响应: %s", mode_as_status_result)
                _LOGGER.debug("ES.GetMode 响应数据: %s", status_data)

                # SOC 与 功率
                battery_soc = status_data.get("bat_soc", result_data.get("battery_soc", 0))
                result_data["battery_soc"] = battery_soc
                ongrid_power = status_data.get("ongrid_power", result_data.get("battery_power", 0))
                result_data["battery_power"] = abs(ongrid_power)

                # 运行模式与电池状态
                device_mode = status_data.get("mode", "Unknown")
                result_data["device_mode"] = device_mode
                if ongrid_power > 0:
                    battery_status = "Selling"
                elif ongrid_power < 0:
                    battery_status = "Charging"
                else:
                    battery_status = "Idle"
                result_data["battery_status"] = battery_status

                _LOGGER.info(
                    "设备 %s 成功: SOC=%s%%, ongrid_power=%sW(取绝对=%sW), mode=%s, status=%s",
                    self.device_ip,
                    battery_soc,
                    ongrid_power,
                    result_data["battery_power"],
                    device_mode,
                    battery_status,
                )
                return True
            except Exception as err:
                _LOGGER.debug("ES.GetMode 查询失败(2.5s超时或异常): %s %s", self.device_ip, str(err))
                return False
        
        # 已并入 es_status_request，不再单独发送第二次
        async def es_mode_request():
            return True
        
        # 串行执行请求，避免UDP客户端冲突
        try:
            # 仅发送一次 ES.GetMode，避免频繁请求导致设备拒绝或丢包
            await es_status_request()
            
        except Exception as err:
            _LOGGER.error("设备 %s 轮询异常: %s", self.device_ip, err)
        
        _LOGGER.info("设备 %s 轮询完成: 电量 %s%%, 功率 %sW, 模式 %s, 状态 %s", 
                    self.device_ip, result_data["battery_soc"], result_data["battery_power"],
                    result_data["device_mode"], result_data["battery_status"])
        
        return result_data


class MarstekSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Marstek sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_info: dict[str, Any],
        sensor_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_info = device_info
        self._sensor_type = sensor_type
        self._attr_device_info = {
            # 用IP作为设备标识，避免MAC重复导致设备被合并
            "identifiers": {(DOMAIN, device_info["ip"])},
            "name": f"Marstek {device_info['device_type']} v{device_info['version']}",
            "manufacturer": "Marstek",
            "model": device_info["device_type"],
            "sw_version": str(device_info["version"]),
            "hw_version": device_info.get("wifi_mac", ""),
        }

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        # 使用IP地址作为唯一标识符，避免MAC地址重复问题
        device_id = self._device_info.get('ip') or self._device_info.get('mac', 'unknown')
        unique_id = f"{device_id}_{self._sensor_type}"
        _LOGGER.debug("生成传感器唯一ID: %s (设备IP: %s, MAC: %s, 传感器类型: %s)", 
                     unique_id, self._device_info.get('ip'), 
                     self._device_info.get('mac'), self._sensor_type)
        return unique_id

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        device_ip = self._device_info.get('ip', 'Unknown')
        sensor_name = self._sensor_type.replace('_', ' ').title()
        return f"Marstek {sensor_name} ({device_ip})"

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._sensor_type)


class MarstekBatterySensor(MarstekSensor):
    """Representation of a Marstek battery sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the battery sensor."""
        super().__init__(coordinator, device_info, "battery_soc")
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:battery"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        device_ip = self._device_info.get('ip', 'Unknown')
        return f"Marstek Battery Level ({device_ip})"

    @property
    def native_value(self) -> int | None:
        """Return the battery level."""
        if not self.coordinator.data:
            return None
        return int(self.coordinator.data.get("battery_soc", 0))


class MarstekPowerSensor(MarstekSensor):
    """Representation of a Marstek power sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the power sensor."""
        super().__init__(coordinator, device_info, "battery_power")
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:flash"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        device_ip = self._device_info.get('ip', 'Unknown')
        return f"Marstek Grid Power ({device_ip})"

    @property
    def native_value(self) -> int | None:
        """Return the battery power."""
        if not self.coordinator.data:
            return None
        return int(self.coordinator.data.get("battery_power", 0))


class MarstekDeviceInfoSensor(MarstekSensor):
    """Representation of a Marstek device info sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_info: dict[str, Any],
        info_type: str,
    ) -> None:
        """Initialize the device info sensor."""
        super().__init__(coordinator, device_info, info_type)
        self._info_type = info_type
        self._attr_icon = "mdi:information"
        # 强制设置为文本型传感器，不显示图形化卡片
        self._attr_device_class = None
        self._attr_state_class = None

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"Marstek {self._info_type.replace('_', ' ').title()}"

    @property
    def native_value(self) -> str | None:
        """Return the device info."""
        if self._info_type == "device_ip":
            return self._device_info.get("ip", "")
        elif self._info_type == "device_version":
            return str(self._device_info.get("version", ""))
        elif self._info_type == "wifi_name":
            return self._device_info.get("wifi_name", "")
        return None


class MarstekDeviceModeSensor(MarstekSensor):
    """Representation of a Marstek device mode sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the device mode sensor."""
        super().__init__(coordinator, device_info, "device_mode")
        self._attr_icon = "mdi:cog"
        # 强制设置为文本型传感器，不显示图形化卡片
        self._attr_device_class = None
        self._attr_state_class = None

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        device_ip = self._device_info.get('ip', 'Unknown')
        return f"Marstek Device Mode ({device_ip})"

    @property
    def native_value(self) -> str | None:
        """Return the device mode."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("device_mode", "Unknown")


class MarstekBatteryStatusSensor(MarstekSensor):
    """Representation of a Marstek battery status sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the battery status sensor."""
        super().__init__(coordinator, device_info, "battery_status")
        self._attr_icon = "mdi:battery"
        # 强制设置为文本型传感器，不显示图形化卡片
        self._attr_device_class = None
        self._attr_state_class = None

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        device_ip = self._device_info.get('ip', 'Unknown')
        return f"Marstek Battery Status ({device_ip})"

    @property
    def native_value(self) -> str | None:
        """Return the battery status."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("battery_status", "Unknown")


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Marstek sensors based on a config entry."""
    device_ip = config_entry.data["host"]
    _LOGGER.info("正在设置Marstek设备传感器: %s", device_ip)
    
    # 使用全局共享的UDP客户端（固定绑定到 192.168.3.235:30000），避免多实例占用端口导致设备不回包
    store = hass.data.setdefault(DOMAIN, {})
    if "udp_client" not in store:
        store["udp_client"] = MarstekUDPClient(hass)
        await store["udp_client"].async_setup()
    udp_client = store["udp_client"]

    # 从配置中获取设备信息
    device_info = {
        "ip": config_entry.data["host"],
        "mac": config_entry.data["mac"],
        "device_type": config_entry.data.get("device_type", "Unknown"),
        "version": config_entry.data.get("version", 0),
        "wifi_name": config_entry.data.get("wifi_name", ""),
        "wifi_mac": config_entry.data.get("wifi_mac", ""),
        "ble_mac": config_entry.data.get("ble_mac", ""),
    }

    # 创建该设备的独立数据更新协调器
    coordinator = MarstekDataUpdateCoordinator(hass, udp_client, device_info["ip"])

    # 创建传感器实体 - 包含电池电量、功率、运行模式、充放电状态、设备IP和版本号
    sensors = [
        MarstekBatterySensor(coordinator, device_info),  # 电池电量
        MarstekPowerSensor(coordinator, device_info),  # 电网功率
        MarstekDeviceModeSensor(coordinator, device_info),  # 设备运行模式
        MarstekBatteryStatusSensor(coordinator, device_info),  # 电池充放电状态
        MarstekDeviceInfoSensor(coordinator, device_info, "device_ip"),  # 设备IP
        MarstekDeviceInfoSensor(coordinator, device_info, "device_version"),  # 版本号
    ]

    _LOGGER.info("设备 %s 传感器设置完成，共创建 %d 个传感器", device_ip, len(sensors))
    async_add_entities(sensors)
