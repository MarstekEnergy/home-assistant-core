"""UDP client for Marstek device communication."""

from __future__ import annotations

import asyncio
import json
import logging
import socket
from typing import Any, Dict, List, Optional, Tuple

from homeassistant.components import network
from homeassistant.core import HomeAssistant

from .const import DEFAULT_UDP_PORT, DISCOVERY_TIMEOUT
from .command_builder import discover

_LOGGER = logging.getLogger(__name__)


class MarstekUDPClient:
    """UDP客户端，用于与Marstek设备通信."""

    def __init__(self, hass: HomeAssistant, port: int = DEFAULT_UDP_PORT) -> None:
        """初始化UDP客户端."""
        self._hass = hass
        self._port = port
        self._socket: Optional[socket.socket] = None
        self._pending_requests: Dict[int, asyncio.Future] = {}
        self._response_cache: Dict[int, Dict[str, Any]] = {}
        self._listen_task: Optional[asyncio.Task] = None
        # 缓存机制
        self._discovery_cache: Optional[List[Dict[str, Any]]] = None
        self._cache_timestamp: float = 0
        self._cache_duration: float = 30.0  # 30秒缓存
        # 固定本地发送IP（用于日志与对端回包识别）
        self._local_send_ip: str = "192.168.3.235"

    async def async_setup(self) -> None:
        """设置UDP socket."""
        if self._socket is not None:
            return

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.setblocking(False)

        # 接收绑定到 0.0.0.0:30000，固定端口
        self._socket.bind(("0.0.0.0", 30000))
        _LOGGER.debug(
            "UDP客户端已绑定到 %s:%s",
            self._socket.getsockname()[0],
            self._socket.getsockname()[1],
        )

    async def async_cleanup(self) -> None:
        """清理UDP socket."""
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass

        if self._socket:
            self._socket.close()
            self._socket = None

    def _get_broadcast_addresses(self) -> List[str]:
        """获取广播地址列表，支持多网卡."""
        addresses = set()
        
        # 添加全网广播
        addresses.add("255.255.255.255")
        
        try:
            # 获取所有网络接口
            import psutil
            for interface, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                        # 计算广播地址
                        if addr.broadcast:
                            addresses.add(addr.broadcast)
                        else:
                            # 如果没有广播地址，计算子网广播地址
                            try:
                                import ipaddress
                                network = ipaddress.IPv4Network(f"{addr.address}/{addr.netmask}", strict=False)
                                addresses.add(str(network.broadcast_address))
                            except Exception:
                                pass
        except ImportError:
            _LOGGER.warning("psutil not available, using only global broadcast")
        except Exception as e:
            _LOGGER.warning("Failed to get network interfaces: %s", e)
        
        # 过滤本机地址，避免处理自己的响应
        try:
            import psutil
            local_ips = set()
            for interface, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == socket.AF_INET:
                        local_ips.add(addr.address)
            addresses = addresses - local_ips
        except Exception:
            pass
            
        return list(addresses)

    def _is_cache_valid(self) -> bool:
        """检查缓存是否有效."""
        if self._discovery_cache is None:
            return False
        current_time = asyncio.get_event_loop().time()
        return (current_time - self._cache_timestamp) < self._cache_duration

    def clear_discovery_cache(self) -> None:
        """清除发现缓存."""
        self._discovery_cache = None
        self._cache_timestamp = 0
        _LOGGER.debug("设备发现缓存已清除")

    async def _send_udp_message(
        self, message: str, target_ip: str, target_port: int
    ) -> None:
        """发送UDP消息到指定目标."""
        if not self._socket:
            await self.async_setup()

        try:
            data = message.encode("utf-8")
            self._socket.sendto(data, (target_ip, target_port))
            # 日志中固定展示本地发送IP与端口
            _LOGGER.info(
                "发送: %s:%d <- %s:%d | %s",
                target_ip,
                target_port,
                self._local_send_ip,
                self._port,
                message,
            )
        except Exception as err:
            _LOGGER.error("发送UDP消息失败: %s", err)
            raise

    async def send_request(
        self, message: str, target_ip: str, target_port: int, timeout: float = 5.0
    ) -> Dict[str, Any]:
        """发送单播请求并等待响应."""
        if not self._socket:
            await self.async_setup()

        # 解析消息获取ID
        try:
            message_obj = json.loads(message)
            request_id = message_obj["id"]
        except (json.JSONDecodeError, KeyError) as e:
            _LOGGER.error("消息格式无效: %s", e)
            raise ValueError(f"Invalid message format: {e}")

        # 创建响应收集的Future
        future = asyncio.Future()
        self._pending_requests[request_id] = future

        try:
            # 启动监听任务（如果还没启动）
            if not self._listen_task or self._listen_task.done():
                self._listen_task = asyncio.create_task(self._listen_for_responses())

            # 发送请求
            await self._send_udp_message(message, target_ip, target_port)

            # 等待响应
            try:
                result = await asyncio.wait_for(future, timeout=timeout)
                return result
            except asyncio.TimeoutError:
                _LOGGER.warning("请求超时: %s:%d", target_ip, target_port)
                raise TimeoutError(f"Request timeout to {target_ip}:{target_port}")

        finally:
            # 清理待响应请求
            if request_id in self._pending_requests:
                self._pending_requests.pop(request_id, None)

    async def _listen_for_responses(self) -> None:
        """监听UDP响应."""
        if not self._socket:
            return

        loop = asyncio.get_event_loop()
        while True:
            try:
                data, addr = await loop.sock_recvfrom(self._socket, 4096)
                response_text = data.decode("utf-8")
                try:
                    response = json.loads(response_text)
                except Exception:
                    response = {"raw": response_text}
                request_id = response.get("id") if isinstance(response, dict) else None
                
                # 日志中固定展示本地接收IP（显示为固定发送IP）与端口
                _LOGGER.info(
                    "响应: %s:%d -> %s:%d | %s",
                    addr[0],
                    addr[1],
                    self._local_send_ip,
                    self._port,
                    json.dumps(response, ensure_ascii=False),
                )
                
                # 存储到响应缓存中 - 参考Node.js的哈希表存储方式
                if request_id:
                    self._response_cache[request_id] = {
                        "response": response,
                        "addr": addr,
                        "timestamp": asyncio.get_event_loop().time(),
                    }
                
                # 对于单播请求，立即resolve
                if request_id and request_id in self._pending_requests:
                    future = self._pending_requests.pop(request_id)
                    if not future.done():
                        future.set_result(response)  # 直接返回响应，不包装
                        
            except asyncio.CancelledError:
                break
            except Exception as err:
                _LOGGER.error("接收UDP响应时出错: %s", err)
                await asyncio.sleep(1)

    async def send_broadcast_request(
        self, message: str, timeout: float = DISCOVERY_TIMEOUT
    ) -> List[Dict[str, Any]]:
        """发送广播请求并收集所有响应."""
        if not self._socket:
            await self.async_setup()

        # 解析消息获取ID
        try:
            message_obj = json.loads(message)
            request_id = message_obj["id"]
        except (json.JSONDecodeError, KeyError) as e:
            _LOGGER.error("消息格式无效: %s", e)
            return []

        responses = []
        start_time = asyncio.get_event_loop().time()

        # 创建响应收集的Future
        future = asyncio.Future()
        self._pending_requests[request_id] = future

        try:
            # 启动监听任务
            if not self._listen_task or self._listen_task.done():
                self._listen_task = asyncio.create_task(self._listen_for_responses())

            # 发送广播请求
            broadcast_addresses = self._get_broadcast_addresses()
            _LOGGER.info("广播目标地址: %s", broadcast_addresses)
            
            for address in broadcast_addresses:
                await self._send_udp_message(message, address, self._port)
                _LOGGER.info("已发送到 %s:%s", address, self._port)

            _LOGGER.info("发送广播请求到 %d 个网络接口", len(broadcast_addresses))
            _LOGGER.info("广播请求内容: %s", message)
            _LOGGER.info("目标端口: %s", self._port)

            # 等待响应 - 参考Node.js的哈希表轮询方式
            _LOGGER.info("开始等待响应，超时时间: %d 秒", timeout)
            try:
                while (asyncio.get_event_loop().time() - start_time) < timeout:
                    # 检查响应缓存中是否有新响应
                    if request_id in self._response_cache:
                        cached_response = self._response_cache[request_id]
                        responses.append(cached_response["response"])
                        _LOGGER.info("广播请求 ID:%s 收到第 %d 个响应", request_id, len(responses))
                        # 移除已处理的缓存响应
                        del self._response_cache[request_id]
                    
                    # 等待一小段时间再检查
                    await asyncio.sleep(0.1)
                    
                    # 检查是否超时
                    if (asyncio.get_event_loop().time() - start_time) >= timeout:
                        _LOGGER.info("广播请求 ID:%s 等待超时", request_id)
                        break

            except Exception as e:
                _LOGGER.error("等待响应时发生错误: %s", e)

        finally:
            # 清理待响应请求
            if request_id in self._pending_requests:
                self._pending_requests.pop(request_id, None)

        _LOGGER.info("广播发现完成，收到 %d 个响应", len(responses))
        return responses

    async def discover_devices(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        """发现网络中的Marstek设备，等待10秒收集所有响应并去重."""
        # 检查缓存
        if use_cache and self._is_cache_valid():
            _LOGGER.debug("使用缓存的设备发现结果")
            return self._discovery_cache.copy()
        
        devices = []
        seen_devices = set()  # 用于去重，基于MAC地址或IP地址
        
        try:
            # 发送广播发现请求，等待10秒收集所有响应
            discover_command = discover()
            responses = await self.send_broadcast_request(discover_command)
            
            for response in responses:
                if response.get("result"):
                    # 解析设备信息
                    device_info = response["result"]
                    
                    # 获取设备唯一标识符（优先使用IP地址，因为MAC可能重复）
                    device_id = (
                        device_info.get("ip", "") or
                        device_info.get("ble_mac") or 
                        device_info.get("wifi_mac") or 
                        f"device_{int(asyncio.get_event_loop().time())}_{hash(str(device_info)) % 10000}"
                    )
                    
                    # 去重检查
                    if device_id in seen_devices:
                        _LOGGER.debug("跳过重复设备: %s (IP: %s, BLE_MAC: %s, WiFi_MAC: %s)", 
                                     device_id, device_info.get("ip"), 
                                     device_info.get("ble_mac"), device_info.get("wifi_mac"))
                        continue
                    
                    seen_devices.add(device_id)
                    _LOGGER.debug("添加新设备: %s (IP: %s, BLE_MAC: %s, WiFi_MAC: %s)", 
                                 device_id, device_info.get("ip"), 
                                 device_info.get("ble_mac"), device_info.get("wifi_mac"))
                    
                    # 构建完整的设备信息
                    device = {
                        "id": device_info.get("id", 0),
                        "device_type": device_info.get("device", "Unknown"),  # 设备类型
                        "version": device_info.get("ver", 0),  # 版本号
                        "wifi_name": device_info.get("wifi_name", ""),  # WiFi名称
                        "ip": device_info.get("ip", ""),  # IP地址
                        "wifi_mac": device_info.get("wifi_mac", ""),  # WiFi MAC
                        "ble_mac": device_info.get("ble_mac", ""),  # BLE MAC
                        "mac": device_info.get("wifi_mac") or device_info.get("ble_mac", ""),  # 兼容性字段
                        "model": device_info.get("device", "Unknown"),  # 兼容性字段
                        "firmware": str(device_info.get("ver", 0)),  # 兼容性字段
                    }
                    
                    devices.append(device)
                    _LOGGER.info("发现设备: Type=%s, Version=%s, WiFi=%s, IP=%s, MAC=%s", 
                               device["device_type"], device["version"], 
                               device["wifi_name"], device["ip"], device["mac"])
                
        except Exception as err:
            _LOGGER.error("设备发现失败: %s", err)
            
        # 更新缓存
        self._discovery_cache = devices.copy()
        self._cache_timestamp = asyncio.get_event_loop().time()
        
        _LOGGER.info("设备发现完成，共发现 %d 个唯一设备", len(devices))
        return devices
