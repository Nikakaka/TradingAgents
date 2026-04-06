"""
Broker integrations for TradingAgents.

Supported integrations:
- Position file parser (Tongdaxin, CSV, Excel exports)
"""

from .position_parser import PositionParser, Position, AccountInfo

# Backward compatibility
GuosenBroker = PositionParser

__all__ = [
    "PositionParser",
    "Position",
    "AccountInfo",
    "GuosenBroker",  # Backward compatibility
]
