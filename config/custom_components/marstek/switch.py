"""Switch platform for Marstek devices."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
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


class MarstekSwitch(SwitchEntity):
    """Base class for Marstek switches."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_info: dict[str, Any],
        switch_type: str,
    ) -> None:
        """Initialize the switch."""
        self.coordinator = coordinator
        self._device_info = device_info
        self._switch_type = switch_type
        self._device_ip = device_info["ip"]
        self._udp_client = None

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        device_id = self._device_info.get('ip') or self._device_info.get('mac', 'unknown')
        return f"{device_id}_{self._switch_type}"

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        device_ip = self._device_info.get('ip', 'Unknown')
        return f"Marstek {self._switch_type.replace('_', ' ').title()} ({device_ip})"

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
    def is_on(self) -> bool | None:
        """Return if the switch is on."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(f"{self._switch_type}_enabled", False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._send_control_command(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._send_control_command(False)

    async def _send_control_command(self, enable: bool) -> None:
        """Send control command to device."""
        if not self._udp_client:
            _LOGGER.error("UDP客户端未初始化")
            return

        try:
            if self._switch_type == "charge_enable":
                power = -1300 if enable else 0
                command = set_es_mode_manual_charge(0, power)
            elif self._switch_type == "discharge_enable":
                power = 1300 if enable else 0
                command = set_es_mode_manual_discharge(0, power)
            elif self._switch_type == "auto_mode":
                if enable:
                    # 切换到自动模式
                    config = {"mode": "Auto"}
                    command = build_command(CMD_ES_SET_MODE, {"id": 0, "config": config})
                else:
                    # 切换到手动模式
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
            else:
                _LOGGER.error("未知的开关类型: %s", self._switch_type)
                return

            _LOGGER.info("发送控制命令到设备 %s: %s", self._device_ip, command)
            result = await self._udp_client.send_request(
                command, self._device_ip, self._udp_client._port, timeout=5.0
            )
            
            # 判断结果：根据 API 文档，ES.SetMode 返回 result.set_result 布尔值
            if result.get("result", {}).get("set_result"):
                _LOGGER.info("设备 %s 控制命令执行成功", self._device_ip)
                # 更新本地状态
                if not self.coordinator.data:
                    self.coordinator.data = {}
                self.coordinator.data[f"{self._switch_type}_enabled"] = enable
            else:
                _LOGGER.error("设备 %s 控制命令执行失败: %s", self._device_ip, result)
                
        except Exception as err:
            _LOGGER.error("发送控制命令失败: %s", str(err))


class MarstekChargeSwitch(MarstekSwitch):
    """Representation of a Marstek charge switch."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the charge switch."""
        super().__init__(coordinator, device_info, "charge_enable")
        self._attr_icon = "mdi:battery-charging"


class MarstekDischargeSwitch(MarstekSwitch):
    """Representation of a Marstek discharge switch."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the discharge switch."""
        super().__init__(coordinator, device_info, "discharge_enable")
        self._attr_icon = "mdi:battery-minus"


class MarstekAutoModeSwitch(MarstekSwitch):
    """Representation of a Marstek auto mode switch."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the auto mode switch."""
        super().__init__(coordinator, device_info, "auto_mode")
        self._attr_icon = "mdi:cog-auto"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Marstek switches based on a config entry."""
    device_ip = config_entry.data["host"]
    _LOGGER.info("正在设置Marstek设备开关: %s", device_ip)
    
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

    # 创建开关实体
    switches = [
        MarstekChargeSwitch(coordinator, device_info),  # 充电开关
        MarstekDischargeSwitch(coordinator, device_info),  # 放电开关
        MarstekAutoModeSwitch(coordinator, device_info),  # 自动模式开关
    ]

    # 为每个开关设置UDP客户端引用（复用全局实例）
    for switch in switches:
        switch._udp_client = udp_client

    _LOGGER.info("设备 %s 开关设置完成，共创建 %d 个开关", device_ip, len(switches))
    async_add_entities(switches)
