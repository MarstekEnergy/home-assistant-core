"""The Marstek integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
import voluptuous as vol
from homeassistant.helpers import config_validation as cv
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .command_builder import build_command, CMD_ES_SET_MODE
from . import device_action  # 注册设备动作适配
from .udp_client import MarstekUDPClient

_LOGGER = logging.getLogger(__name__)

# 仅加载用于展示的传感器实体，控制能力由服务（charge/discharge/stop）提供
PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Marstek component."""
    _LOGGER.info("Marstek组件已加载")
    
    # 确保配置流程被正确注册
    try:
        from . import config_flow
        _LOGGER.info("Marstek配置流程已导入")
    except Exception as e:
        _LOGGER.error("Marstek配置流程导入失败: %s", e)
    
    # 创建全局共享 UDP 客户端
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    if "udp_client" not in hass.data[DOMAIN]:
        client = MarstekUDPClient(hass)
        hass.loop.create_task(client.async_setup())
        hass.data[DOMAIN]["udp_client"] = client

    # 注册自动化动作服务
    service_schema = vol.Schema(
        {
            vol.Required("host"): cv.string,
            vol.Optional("power"): vol.Coerce(int),
        }
    )

    async def _send_set_mode(host: str, power: int | None, enable: int) -> None:
        udp = hass.data[DOMAIN]["udp_client"]
        # 根据 power 与 enable 组装 ES.SetMode（Manual 模式，全天 00:00-23:59，week_set=127）
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
        await udp.send_request(command, host, udp._port, timeout=5.0)

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
    _LOGGER.info("设置Marstek配置条目: %s", entry.title)
    
    # 设置平台
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # 设备动作由 device_action.py 提供，Home Assistant 会按平台自动发现，无需手动注册

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("卸载Marstek配置条目: %s", entry.title)
    
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    # 如果没有配置条目了，清理全局 UDP 客户端
    if unload_ok and not hass.config_entries.async_entries(DOMAIN):
        client = hass.data.get(DOMAIN, {}).pop("udp_client", None)
        if client:
            await client.async_cleanup()
    
    return unload_ok
