"""Number platform for Marstek devices."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .sensor import MarstekDataUpdateCoordinator
from .udp_client import MarstekUDPClient
from .command_builder import build_command, CMD_ES_SET_MODE

_LOGGER = logging.getLogger(__name__)


class MarstekNumber(NumberEntity):
    """Base class for Marstek numbers."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_info: dict[str, Any],
        number_type: str,
        min_value: float,
        max_value: float,
        step: float,
        unit: str,
    ) -> None:
        """Initialize the number."""
        self.coordinator = coordinator
        self._device_info = device_info
        self._number_type = number_type
        self._device_ip = device_info["ip"]
        self._udp_client = None
        
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        self._attr_mode = NumberMode.BOX

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        device_id = self._device_info.get('ip') or self._device_info.get('mac', 'unknown')
        return f"{device_id}_{self._number_type}"

    @property
    def name(self) -> str:
        """Return the name of the number."""
        device_ip = self._device_info.get('ip', 'Unknown')
        return f"Marstek {self._number_type.replace('_', ' ').title()} ({device_ip})"

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        return {
            # 用IP作为设备标识，避免MAC重复导致设备被合并
            "identifiers": {(DOMAIN, self._device_info["ip"])},
            "name": f"Marstek {self._device_info['device_type']} v{self._device_info['version']}",
            "manufacturer": "Marstek",
            "model": self._device_info["device_type"],
            "sw_version": str(self._device_info["version"]),
            "hw_version": self._device_info.get("wifi_mac", ""),
        }

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(f"{self._number_type}_value", 0.0)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        await self._send_control_command(value)

    async def _send_control_command(self, value: float) -> None:
        """Send control command to device."""
        if not self._udp_client:
            _LOGGER.error("UDP客户端未初始化")
            return

        try:
            if self._number_type == "charge_power":
                # 充电功率（负数）
                power = int(-abs(value))
                config = {
                    "mode": "Manual",
                    "manual_cfg": {
                        "time_num": 0,
                        "start_time": "00:00",
                        "end_time": "23:59",
                        "week_set": 127,
                        "power": power,
                        "enable": 1 if power != 0 else 0
                    }
                }
            elif self._number_type == "discharge_power":
                # 放电功率（正数）
                power = int(abs(value))
                config = {
                    "mode": "Manual",
                    "manual_cfg": {
                        "time_num": 0,
                        "start_time": "00:00",
                        "end_time": "23:59",
                        "week_set": 127,
                        "power": power,
                        "enable": 1 if power != 0 else 0
                    }
                }
            elif self._number_type == "target_soc":
                # 目标电量设置
                config = {
                    "mode": "Auto",
                    "auto_cfg": {
                        "target_soc": int(value),
                        "enable": 1
                    }
                }
            else:
                _LOGGER.error("未知的数字类型: %s", self._number_type)
                return

            command = build_command(CMD_ES_SET_MODE, {"id": 0, "config": config})
            _LOGGER.info("发送功率控制命令到设备 %s: %s", self._device_ip, command)
            
            result = await self._udp_client.send_request(
                command, self._device_ip, self._udp_client._port, timeout=5.0
            )
            
            # 判断结果：根据 API 文档，ES.SetMode 返回 result.set_result 布尔值
            if result.get("result", {}).get("set_result"):
                _LOGGER.info("设备 %s 功率控制命令执行成功，设置值: %s", self._device_ip, value)
                # 更新本地状态
                if not self.coordinator.data:
                    self.coordinator.data = {}
                self.coordinator.data[f"{self._number_type}_value"] = value
            else:
                _LOGGER.error("设备 %s 功率控制命令执行失败: %s", self._device_ip, result)
                
        except Exception as err:
            _LOGGER.error("发送功率控制命令失败: %s", str(err))


class MarstekChargePowerNumber(MarstekNumber):
    """Representation of a Marstek charge power number."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the charge power number."""
        super().__init__(
            coordinator, device_info, "charge_power", 
            0, 2000, 100, "W"
        )
        self._attr_icon = "mdi:battery-charging"


class MarstekDischargePowerNumber(MarstekNumber):
    """Representation of a Marstek discharge power number."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the discharge power number."""
        super().__init__(
            coordinator, device_info, "discharge_power", 
            0, 2000, 100, "W"
        )
        self._attr_icon = "mdi:battery-minus"


class MarstekTargetSOCNumber(MarstekNumber):
    """Representation of a Marstek target SOC number."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the target SOC number."""
        super().__init__(
            coordinator, device_info, "target_soc", 
            0, 100, 5, "%"
        )
        self._attr_icon = "mdi:battery-heart"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Marstek numbers based on a config entry."""
    device_ip = config_entry.data["host"]
    _LOGGER.info("正在设置Marstek设备数值控制: %s", device_ip)
    
    # 复用全局共享的UDP客户端
    store = hass.data.setdefault(DOMAIN, {})
    if "udp_client" not in store:
        store["udp_client"] = MarstekUDPClient(hass)
        await store["udp_client"].async_setup()
    udp_client: MarstekUDPClient = store["udp_client"]

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

    # 创建数值控制实体
    numbers = [
        MarstekChargePowerNumber(coordinator, device_info),  # 充电功率
        MarstekDischargePowerNumber(coordinator, device_info),  # 放电功率
        MarstekTargetSOCNumber(coordinator, device_info),  # 目标电量
    ]

    # 为每个数值控制设置UDP客户端引用
    for number in numbers:
        number._udp_client = udp_client

    _LOGGER.info("设备 %s 数值控制设置完成，共创建 %d 个数值控制", device_ip, len(numbers))
    async_add_entities(numbers)
