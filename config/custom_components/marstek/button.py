"""Button platform for Marstek devices."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .sensor import MarstekDataUpdateCoordinator
from .udp_client import MarstekUDPClient
from .command_builder import (
    set_es_mode_manual_charge,
    set_es_mode_manual_discharge,
    build_command,
    CMD_ES_SET_MODE,
)

_LOGGER = logging.getLogger(__name__)


class MarstekButton(ButtonEntity):
    """Base class for Marstek buttons."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_info: dict[str, Any],
        button_type: str,
    ) -> None:
        """Initialize the button."""
        self.coordinator = coordinator
        self._device_info = device_info
        self._button_type = button_type
        self._device_ip = device_info["ip"]
        self._udp_client = None

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        device_id = self._device_info.get('ip') or self._device_info.get('mac', 'unknown')
        return f"{device_id}_{self._button_type}"

    @property
    def name(self) -> str:
        """Return the name of the button."""
        device_ip = self._device_info.get('ip', 'Unknown')
        return f"Marstek {self._button_type.replace('_', ' ').title()} ({device_ip})"

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        return {
            # 用IP作为设备标识，和传感器/开关/数值一致，避免分裂成两个设备
            "identifiers": {(DOMAIN, self._device_info["ip"])},
            "name": f"Marstek {self._device_info['device_type']} v{self._device_info['version']}",
            "manufacturer": "Marstek",
            "model": self._device_info["device_type"],
            "sw_version": str(self._device_info["version"]),
            "hw_version": self._device_info.get("wifi_mac", ""),
        }

    async def async_press(self) -> None:
        """Handle the button press."""
        await self._send_control_command()

    async def _send_control_command(self) -> None:
        """Send control command to device."""
        if not self._udp_client:
            _LOGGER.error("UDP客户端未初始化")
            return

        try:
            if self._button_type == "stop_all":
                # 停止所有充放电
                config = {
                    "mode": "Manual",
                    "manual_cfg": {
                        "time_num": 0,
                        "start_time": "00:00",
                        "end_time": "23:59",
                        "week_set": 127,
                        "power": 0,
                        "enable": 0
                    }
                }
                command = build_command(CMD_ES_SET_MODE, {"id": 0, "config": config})
                
            elif self._button_type == "max_charge":
                # 最大功率充电
                command = set_es_mode_manual_charge(0, -2000)
                
            elif self._button_type == "max_discharge":
                # 最大功率放电
                command = set_es_mode_manual_discharge(0, 2000)
                
            elif self._button_type == "emergency_stop":
                # 紧急停止
                config = {
                    "mode": "Passive",
                    "passive_cfg": {
                        "enable": 1
                    }
                }
                command = build_command(CMD_ES_SET_MODE, {"id": 0, "config": config})
                
            else:
                _LOGGER.error("未知的按钮类型: %s", self._button_type)
                return

            _LOGGER.info("发送快捷操作命令到设备 %s: %s", self._device_ip, command)
            result = await self._udp_client.send_request(
                command, self._device_ip, self._udp_client._port, timeout=5.0
            )
            
            # 判断结果：根据 API 文档，ES.SetMode 返回 result.set_result 布尔值
            if result.get("result", {}).get("set_result"):
                _LOGGER.info("设备 %s 快捷操作命令执行成功: %s", self._device_ip, self._button_type)
            else:
                _LOGGER.error("设备 %s 快捷操作命令执行失败: %s", self._device_ip, result)
                
        except Exception as err:
            _LOGGER.error("发送快捷操作命令失败: %s", str(err))


class MarstekStopAllButton(MarstekButton):
    """Representation of a Marstek stop all button."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the stop all button."""
        super().__init__(coordinator, device_info, "stop_all")
        self._attr_icon = "mdi:stop-circle"


class MarstekMaxChargeButton(MarstekButton):
    """Representation of a Marstek max charge button."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the max charge button."""
        super().__init__(coordinator, device_info, "max_charge")
        self._attr_icon = "mdi:battery-charging-high"


class MarstekMaxDischargeButton(MarstekButton):
    """Representation of a Marstek max discharge button."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the max discharge button."""
        super().__init__(coordinator, device_info, "max_discharge")
        self._attr_icon = "mdi:battery-minus-variant"


class MarstekEmergencyStopButton(MarstekButton):
    """Representation of a Marstek emergency stop button."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the emergency stop button."""
        super().__init__(coordinator, device_info, "emergency_stop")
        self._attr_icon = "mdi:alert-octagon"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Marstek buttons based on a config entry."""
    device_ip = config_entry.data["host"]
    _LOGGER.info("正在设置Marstek设备按钮: %s", device_ip)
    
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

    # 创建按钮实体
    buttons = [
        MarstekStopAllButton(coordinator, device_info),  # 停止所有
        MarstekMaxChargeButton(coordinator, device_info),  # 最大充电
        MarstekMaxDischargeButton(coordinator, device_info),  # 最大放电
        MarstekEmergencyStopButton(coordinator, device_info),  # 紧急停止
    ]

    # 为每个按钮设置UDP客户端引用
    for button in buttons:
        button._udp_client = udp_client

    _LOGGER.info("设备 %s 按钮设置完成，共创建 %d 个按钮", device_ip, len(buttons))
    async_add_entities(buttons)
