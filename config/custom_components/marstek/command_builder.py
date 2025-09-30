"""Command builder for Marstek devices."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from .const import (
    CMD_DISCOVER,
    CMD_BATTERY_STATUS,
    CMD_ES_STATUS,
    CMD_ES_MODE,
    CMD_ES_SET_MODE,
)

# 请求ID计数器
_request_id = 0


def get_next_request_id() -> int:
    """获取下一个请求ID."""
    global _request_id
    _request_id += 1
    return _request_id


def reset_request_id() -> None:
    """重置请求ID计数器."""
    global _request_id
    _request_id = 0


def build_command(method: str, params: Optional[Dict[str, Any]] = None) -> str:
    """构建指令JSON字符串."""
    command = {
        "id": get_next_request_id(),
        "method": method,
        "params": params or {},
    }
    return json.dumps(command)


def discover() -> str:
    """设备发现指令."""
    return build_command(CMD_DISCOVER, {"ble_mac": "0"})


def get_battery_status(device_id: int = 0) -> str:
    """电池状态查询指令."""
    return build_command(CMD_BATTERY_STATUS, {"id": device_id})


def get_es_status(device_id: int = 0) -> str:
    """获取设备电力状态与统计数据指令."""
    return build_command(CMD_ES_STATUS, {"id": device_id})


def get_es_mode(device_id: int = 0) -> str:
    """获取设备运行模式与电量信息指令."""
    return build_command(CMD_ES_MODE, {"id": device_id})


def set_es_mode_manual_charge(device_id: int = 0, power: int = -1300) -> str:
    """设置手动充电模式指令."""
    config = {
        "mode": "Manual",
        "manual_cfg": {
            "time_num": 0,
            "start_time": "00:00",
            "end_time": "23:59",
            "week_set": 127,  # 二进制代表每天都这样
            "power": power,  # 负数代表充电
            "enable": 1
        }
    }
    return build_command(CMD_ES_SET_MODE, {"id": device_id, "config": config})


def set_es_mode_manual_discharge(device_id: int = 0, power: int = 1300) -> str:
    """设置手动放电模式指令."""
    config = {
        "mode": "Manual",
        "manual_cfg": {
            "time_num": 0,
            "start_time": "00:00",
            "end_time": "23:59",
            "week_set": 127,  # 二进制代表每天都这样
            "power": power,  # 正数代表放电
            "enable": 1
        }
    }
    return build_command(CMD_ES_SET_MODE, {"id": device_id, "config": config})
