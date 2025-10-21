"""The Marstek integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .command_builder import CMD_ES_SET_MODE, build_command
from .const import DEFAULT_UDP_PORT, DOMAIN
from .udp_client import MarstekUDPClient

_LOGGER = logging.getLogger(__name__)

# Only load sensor platform for display; control via services (charge/discharge/stop)
PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Marstek component."""
    _LOGGER.info("Marstek integration loaded")

    # Config flow will be auto-discovered by Home Assistant

    # Create global shared UDP client
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    if "udp_client" not in hass.data[DOMAIN]:
        client = MarstekUDPClient(hass)
        hass.loop.create_task(client.async_setup())
        hass.data[DOMAIN]["udp_client"] = client

    # Register automation action services
    service_schema = vol.Schema(
        {
            vol.Required("host"): cv.string,
            vol.Optional("power"): vol.Coerce(int),
        }
    )

    async def _send_set_mode(host: str, power: int | None, enable: int) -> None:
        udp = hass.data[DOMAIN]["udp_client"]
        # Assemble ES.SetMode for Manual mode (00:00-23:59, week_set=127)
        cfg_power = int(power or 0)
        payload = {
            "id": 0,
            "config": {
                "mode": "Manual",
                "manual_cfg": {
                    "time_num": 0,
                    "start_time": "00:00",
                    "end_time": "23:59",
                    "week_set": 127,
                    "power": cfg_power,
                    "enable": enable,
                },
            },
        }
        command = build_command(CMD_ES_SET_MODE, payload)
        await udp.send_request(command, host, DEFAULT_UDP_PORT, timeout=5.0)

    async def _handle_charge(call) -> None:
        host: str = call.data["host"]
        power: int = call.data.get("power", -1300)
        if power > 0:
            power = -abs(power)
        await _send_set_mode(host, power, enable=1)

    async def _handle_discharge(call) -> None:
        host: str = call.data["host"]
        power: int = call.data.get("power", 1300)
        if power < 0:
            power = abs(power)
        await _send_set_mode(host, power, enable=1)

    async def _handle_stop(call) -> None:
        host: str = call.data["host"]
        await _send_set_mode(host, 0, enable=0)

    hass.services.async_register(DOMAIN, "charge", _handle_charge, schema=service_schema)
    hass.services.async_register(DOMAIN, "discharge", _handle_discharge, schema=service_schema)
    hass.services.async_register(DOMAIN, "stop", _handle_stop, schema=vol.Schema({vol.Required("host"): cv.string}))

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Marstek from a config entry."""
    _LOGGER.info("Setting up Marstek config entry: %s", entry.title)

    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Device actions are provided by device_action.py and discovered by HA

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Marstek config entry: %s", entry.title)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Cleanup global UDP client if no entries remain
    if unload_ok and not hass.config_entries.async_entries(DOMAIN):
        client = hass.data.get(DOMAIN, {}).pop("udp_client", None)
        if client:
            await client.async_cleanup()

    return unload_ok
