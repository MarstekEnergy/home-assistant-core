"""Sensor platform for Marstek devices."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .command_builder import get_es_mode
from .const import DEFAULT_UDP_PORT, DOMAIN
from .udp_client import MarstekUDPClient

_LOGGER = logging.getLogger(__name__)

# Update interval for polling device data
SCAN_INTERVAL = timedelta(seconds=10)


class MarstekDataUpdateCoordinator(DataUpdateCoordinator):
    """Per-device data update coordinator."""

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
        _LOGGER.debug("Device %s polling coordinator started, interval: %ss", device_ip, SCAN_INTERVAL.total_seconds())

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch all data using a single ES.GetMode request."""
        _LOGGER.debug("Start polling device: %s", self.device_ip)
        _LOGGER.debug("UDP client: %s", self.udp_client)

        # Use existing data as defaults (preserve previous values)
        current_data = self.data or {}
        result_data = {
            "battery_soc": current_data.get("battery_soc", 0),
            "battery_power": current_data.get("battery_power", 0),
            "device_mode": current_data.get("device_mode", "Unknown"),
            "battery_status": current_data.get("battery_status", "Unknown"),
            "device_ip": self.device_ip,
            "last_update": asyncio.get_event_loop().time(),
        }

        # Delay helper
        def delay(ms):
            return asyncio.sleep(ms / 1000.0)

        # Single ES.GetMode request (includes bat_soc and ongrid_power)
        async def es_status_request():
            try:
                _LOGGER.debug("Begin ES.GetMode query to device: %s", self.device_ip)
                mode_as_status_command = get_es_mode(0)
                _LOGGER.debug("Sensor send -> %s | %s", self.device_ip, mode_as_status_command)
                # Wait up to 2.5s
                mode_as_status_result = await self.udp_client.send_request(
                    mode_as_status_command, self.device_ip, DEFAULT_UDP_PORT, timeout=2.5
                )
                _LOGGER.debug("Sensor recv <- %s | %s", self.device_ip, mode_as_status_result)

                status_data = mode_as_status_result.get("result", {})
                _LOGGER.debug("ES.GetMode raw: %s", mode_as_status_result)
                _LOGGER.debug("ES.GetMode data: %s", status_data)

                # SOC and power
                battery_soc = status_data.get("bat_soc", result_data.get("battery_soc", 0))
                result_data["battery_soc"] = battery_soc
                ongrid_power = status_data.get("ongrid_power", result_data.get("battery_power", 0))
                result_data["battery_power"] = abs(ongrid_power)

                # Operating mode and battery status
                device_mode = status_data.get("mode", "Unknown")
                result_data["device_mode"] = device_mode
                if ongrid_power > 0:
                    battery_status = "Selling"
                elif ongrid_power < 0:
                    battery_status = "Charging"
                else:
                    battery_status = "Idle"
                result_data["battery_status"] = battery_status

                _LOGGER.debug(
                    "Device %s OK: SOC=%s%%, ongrid_power=%sW(abs=%sW), mode=%s, status=%s",
                    self.device_ip,
                    battery_soc,
                    ongrid_power,
                    result_data["battery_power"],
                    device_mode,
                    battery_status,
                )
            except (TimeoutError, OSError, ValueError) as err:
                _LOGGER.debug("ES.GetMode failed (timeout/exception): %s %s", self.device_ip, str(err))
                return False
            else:
                return True

        # Already covered by es_status_request, keep for structure compatibility
        async def es_mode_request():
            return True

        # Execute sequentially to avoid UDP client conflicts
        try:
            # Only send once to avoid throttling or packet loss
            await es_status_request()
        except (TimeoutError, OSError, ValueError) as err:
            _LOGGER.error("Device %s polling error: %s", self.device_ip, err)

        _LOGGER.debug(
            "Device %s poll done: SOC %s%%, Power %sW, Mode %s, Status %s",
            self.device_ip,
            result_data["battery_soc"],
            result_data["battery_power"],
            result_data["device_mode"],
            result_data["battery_status"],
        )

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
            # Use IP as identifier to avoid merge on duplicate MACs
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
        # Use IP as unique identifier to avoid duplicate MAC collisions
        device_id = self._device_info.get('ip') or self._device_info.get('mac', 'unknown')
        unique_id = f"{device_id}_{self._sensor_type}"
        _LOGGER.debug(
            "Generate sensor unique_id: %s (ip=%s, mac=%s, type=%s)",
            unique_id,
            self._device_info.get('ip'),
            self._device_info.get('mac'),
            self._sensor_type,
        )
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
        # Force as text sensor to avoid graph cards
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
        if self._info_type == "device_version":
            return str(self._device_info.get("version", ""))
        if self._info_type == "wifi_name":
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
        # Force as text sensor to avoid graph cards
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
        # Force as text sensor to avoid graph cards
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
    _LOGGER.info("Setting up Marstek sensors: %s", device_ip)

    # Use a shared global UDP client to avoid port conflicts across instances
    store = hass.data.setdefault(DOMAIN, {})
    if "udp_client" not in store:
        store["udp_client"] = MarstekUDPClient(hass)
        await store["udp_client"].async_setup()
    udp_client = store["udp_client"]

    # Build device info from config entry
    device_info = {
        "ip": config_entry.data["host"],
        "mac": config_entry.data["mac"],
        "device_type": config_entry.data.get("device_type", "Unknown"),
        "version": config_entry.data.get("version", 0),
        "wifi_name": config_entry.data.get("wifi_name", ""),
        "wifi_mac": config_entry.data.get("wifi_mac", ""),
        "ble_mac": config_entry.data.get("ble_mac", ""),
    }

    # Create coordinator for this device
    coordinator = MarstekDataUpdateCoordinator(hass, udp_client, device_info["ip"])

    # Create sensor entities - battery SoC, grid power, device mode, battery status, device IP, version
    sensors = [
        MarstekBatterySensor(coordinator, device_info),  # 电池电量
        MarstekPowerSensor(coordinator, device_info),  # 电网功率
        MarstekDeviceModeSensor(coordinator, device_info),  # 设备运行模式
        MarstekBatteryStatusSensor(coordinator, device_info),  # 电池充放电状态
        MarstekDeviceInfoSensor(coordinator, device_info, "device_ip"),  # 设备IP
        MarstekDeviceInfoSensor(coordinator, device_info, "device_version"),  # 版本号
    ]

    _LOGGER.info("Device %s sensors set up, total %d", device_ip, len(sensors))
    async_add_entities(sensors)
