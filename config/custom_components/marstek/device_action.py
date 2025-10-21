"""Device actions for Marstek.

让用户在“设备动作”里直接选择：充电/放电/停止。
功率写死：充电 -1300W，放电 1300W；停止 enable=0。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .command_builder import CMD_ES_SET_MODE, build_command
from .const import DEFAULT_UDP_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


ACTION_CHARGE = "charge"
ACTION_DISCHARGE = "discharge"
ACTION_STOP = "stop"


# 设备动作配置校验模式
ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_DOMAIN): vol.In((DOMAIN,)),
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required(CONF_TYPE): vol.In((ACTION_CHARGE, ACTION_DISCHARGE, ACTION_STOP)),
        # 前端有时会携带 entity_id（即使设备动作不需要），放宽为可选以通过校验
        vol.Optional("entity_id"): cv.entity_id,
    }
)


async def async_get_actions(hass: HomeAssistant, device_id: str) -> list[dict[str, Any]]:
    """List device actions for a Marstek device."""
    actions: list[dict[str, Any]] = []

    # Only expose actions for this integration
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get(device_id)
    if not device:
        return actions

    if not any(ident[0] == DOMAIN for ident in device.identifiers):
        return actions

    actions.extend(
        {
            "domain": DOMAIN,
            "type": action,
            "device_id": device_id,
        }
        for action in (ACTION_CHARGE, ACTION_DISCHARGE, ACTION_STOP)
    )

    return actions


async def _get_host_from_device(hass: HomeAssistant, device_id: str) -> str | None:
    """Resolve device IP(host) via device registry and config entries.

    Identifiers are (DOMAIN, ip), so read IP directly; fallback to config entry host.
    """
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get(device_id)
    if not device:
        return None

    # 首选 identifiers 中的 IP
    for domain, identifier in device.identifiers:
        if domain == DOMAIN:
            return identifier

    # 兜底：找关联的配置项
    for entry_id in device.config_entries:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry and entry.domain == DOMAIN:
            return entry.data.get("host")

    return None


async def async_call_action_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    variables: dict[str, Any],
    context: Any,
) -> None:
    """Execute a device action."""
    action_type: str = config.get("type")
    device_id: str = config.get("device_id")

    host = await _get_host_from_device(hass, device_id)
    if not host:
        return

    # Charge/Discharge/Stop: 00:00-23:59, week_set=127
    if action_type == ACTION_CHARGE:
        power = -1300
        enable = 1
    elif action_type == ACTION_DISCHARGE:
        power = 1300
        enable = 1
    elif action_type == ACTION_STOP:
        power = 0
        enable = 0
    else:
        return

    payload = {
        "id": 0,
        "config": {
            "mode": "Manual",
            "manual_cfg": {
                "time_num": 0,
                "start_time": "00:00",
                "end_time": "23:59",
                "week_set": 127,
                "power": power,
                "enable": enable,
            },
        },
    }
    command = build_command(CMD_ES_SET_MODE, payload)

    # Send via global UDP client
    udp = hass.data.get(DOMAIN, {}).get("udp_client")
    if not udp:
        return

    # Retry up to 5 times with 2s delay
    max_retries = 5
    retry_delay = 2.0

    for attempt in range(max_retries):
        try:
            await udp.send_request(command, host, DEFAULT_UDP_PORT, timeout=8.0)
        except (TimeoutError, OSError, ValueError) as e:
            if attempt < max_retries - 1:
                action_name = {"charge": "charge", "discharge": "discharge", "stop": "stop"}.get(action_type, action_type)
                _LOGGER.warning(
                    "Action %s attempt %d failed (device: %s): %s, retry in %d s",
                    action_name, attempt + 1, host, str(e), int(retry_delay)
                )
                await asyncio.sleep(retry_delay)
            else:
                action_name = {"charge": "charge", "discharge": "discharge", "stop": "stop"}.get(action_type, action_type)
                _LOGGER.error(
                    "Action %s failed after %d retries (device: %s): %s",
                    action_name, max_retries, host, str(e)
                )
                raise
        else:
            return


async def async_get_action_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, Any]:
    """List action capabilities.

    注意：这里必须返回一个 voluptuous 的 Schema，而不是列表。
    返回空 Schema 表示无额外字段，避免前端转换报错。
    """
    return {"extra_fields": vol.Schema({})}


