"""Config flow for Marstek integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .udp_client import MarstekUDPClient

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_MAC): str,
    }
)


class MarstekConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Marstek."""

    VERSION = 1
    domain = DOMAIN

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - broadcast device discovery."""
        if user_input is not None:
            # User has selected a device from the discovered list
            device_index = int(user_input["device"])
            device = self.discovered_devices[device_index]
            
            # Check if device is already configured (使用IP地址作为唯一标识符)
            unique_id = device["ip"] or device["mac"]
            _LOGGER.info("检查设备唯一性: IP=%s, MAC=%s, 唯一ID=%s", 
                        device["ip"], device["mac"], unique_id)
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"Marstek {device['device_type']} v{device['version']} ({device['ip']})",
                data={
                    CONF_HOST: device["ip"],
                    CONF_MAC: device["mac"],
                    "device_type": device["device_type"],
                    "version": device["version"],
                    "wifi_name": device["wifi_name"],
                    "wifi_mac": device["wifi_mac"],
                    "ble_mac": device["ble_mac"],
                    "model": device["model"],  # 兼容性字段
                    "firmware": device["firmware"],  # 兼容性字段
                },
            )

        # Start broadcast device discovery
        try:
            _LOGGER.info("开始发现设备...")
            udp_client = MarstekUDPClient(self.hass)
            await udp_client.async_setup()
            
            # 执行广播发现，参考Node.js代码的重试机制
            devices = await self._discover_devices_with_retry(udp_client)
            await udp_client.async_cleanup()
            
            if not devices:
                return self.async_show_form(
                    step_id="user",
                    data_schema=vol.Schema({}),
                    errors={"base": "no_devices_found"},
                )
            
            # Store discovered devices for selection
            self.discovered_devices = devices
            _LOGGER.info(f"发现 {len(devices)} 个设备")
            
            # Show device selection form with detailed device information
            device_options = {}
            for i, device in enumerate(devices):
                # 构建详细的设备显示名称，包含所有重要信息
                device_name = (
                    f"{device.get('device_type', 'Unknown')} "
                    f"v{device.get('version', 'Unknown')} "
                    f"({device.get('wifi_name', 'No WiFi')}) "
                    f"- {device.get('ip', 'Unknown')}"
                )
                device_options[str(i)] = device_name
            
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required("device"): vol.In(device_options)
                }),
                description_placeholders={
                    "devices": "\n".join([f"- {name}" for name in device_options.values()])
                }
            )
            
        except Exception as err:
            _LOGGER.error("设备发现失败: %s", err)
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({}),
                errors={"base": "discovery_failed"},
            )

    async def _discover_devices_with_retry(self, udp_client, max_retries=2, retry_delay=3000):
        """设备发现重试机制，参考Node.js代码"""
        for attempt in range(1, max_retries + 1):
            try:
                if attempt > 1:
                    _LOGGER.info(f"设备发现，第 {attempt} 次重试...")
                    await asyncio.sleep(retry_delay / 1000)  # 转换为秒
                    # 清除缓存，强制重新发现
                    udp_client.clear_discovery_cache()
                
                # 第一次尝试使用缓存，重试时强制刷新
                use_cache = (attempt == 1)
                devices = await udp_client.discover_devices(use_cache=use_cache)
                
                if devices:
                    if attempt > 1:
                        _LOGGER.info("设备发现重试成功")
                    return devices
                else:
                    _LOGGER.warning(f"第 {attempt} 次尝试未发现设备")
                    
            except Exception as error:
                _LOGGER.error(f"设备发现失败，第 {attempt} 次尝试: {error}")
                
                if attempt == max_retries:
                    _LOGGER.error(f"设备发现失败，已重试 {max_retries} 次: {error}")
                    # 尝试使用缓存数据作为备选
                    if udp_client._discovery_cache:
                        _LOGGER.info("使用缓存的设备数据作为备选")
                        return udp_client._discovery_cache.copy()
                    raise error
        
        return []

    async def async_step_zeroconf(self, discovery_info: dict[str, Any]) -> FlowResult:
        """Handle zeroconf discovery."""
        # This would be used if we implement mDNS discovery in the future
        return await self.async_step_user()


class MarstekOptionsFlow(config_entries.OptionsFlow):
    """Handle Marstek options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({}),
        )
