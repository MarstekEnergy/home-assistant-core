"""Device actions for Marstek.

让用户在“设备动作”里直接选择：充电/放电/停止。
功率写死：充电 -1300W，放电 1300W；停止 enable=0。
"""

from __future__ import annotations

from typing import Any
import voluptuous as vol
import asyncio
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers import config_validation as cv
from homeassistant.const import CONF_DEVICE_ID, CONF_TYPE, CONF_DOMAIN

from .const import DOMAIN
from .command_builder import build_command, CMD_ES_SET_MODE

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

    # 仅对属于本集成的设备暴露动作
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get(device_id)
    if not device:
        return actions

    if not any(ident[0] == DOMAIN for ident in device.identifiers):
        return actions

    for action in (ACTION_CHARGE, ACTION_DISCHARGE, ACTION_STOP):
        actions.append(
            {
                "domain": DOMAIN,
                "type": action,
                "device_id": device_id,
            }
        )

    return actions


async def _get_host_from_device(hass: HomeAssistant, device_id: str) -> str | None:
    """Resolve device IP(host) via device registry and config entries.

    我们在实体里把 identifiers 设为 (DOMAIN, ip)，因此可直接用 identifiers 取 IP。
    兜底：从关联的 config_entry.data["host"] 拿。
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

    # 充/放电/停止：写死全天 00:00-23:59, week_set=127
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

    # 通过全局 UDP 客户端发送
    udp = hass.data.get(DOMAIN, {}).get("udp_client")
    if not udp:
        return
    
    # 重试机制：最多重试3次，间隔2秒
    max_retries = 5
    retry_delay = 2.0
    
    for attempt in range(max_retries):
        try:
            await udp.send_request(command, host, udp._port, timeout=8.0)  # 增加超时到8秒
            # 成功则直接返回
            return
        except Exception as e:
            if attempt < max_retries - 1:  # 不是最后一次尝试
                # 记录重试日志
                action_name = {"charge": "充电", "discharge": "放电", "stop": "停止"}.get(action_type, action_type)
                _LOGGER.warning(
                    "设备动作 %s 第 %d 次尝试失败 (设备: %s): %s，%d 秒后重试",
                    action_name, attempt + 1, host, str(e), int(retry_delay)
                )
                await asyncio.sleep(retry_delay)
            else:
                # 最后一次尝试也失败了，记录错误并抛出异常
                action_name = {"charge": "充电", "discharge": "放电", "stop": "停止"}.get(action_type, action_type)
                _LOGGER.error(
                    "设备动作 %s 重试 %d 次后仍然失败 (设备: %s): %s",
                    action_name, max_retries, host, str(e)
                )
                raise


async def async_get_action_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, Any]:
    """List action capabilities.

    注意：这里必须返回一个 voluptuous 的 Schema，而不是列表。
    返回空 Schema 表示无额外字段，避免前端转换报错。
    """
    return {"extra_fields": vol.Schema({})}


