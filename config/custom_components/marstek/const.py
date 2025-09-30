"""Constants for the Marstek integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "marstek"

# UDP Configuration
DEFAULT_UDP_PORT: Final = 30000
DISCOVERY_TIMEOUT: Final = 10.0  # 每次广播等待10秒

# Device Commands
CMD_DISCOVER: Final = "Marstek.GetDevice"
CMD_BATTERY_STATUS: Final = "Bat.GetStatus"
CMD_ES_STATUS: Final = "ES.GetStatus"
CMD_ES_MODE: Final = "ES.GetMode"
CMD_ES_SET_MODE: Final = "ES.SetMode"
