"""
Abstract base class for all trading strategies.
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from models.signal import Signal

class BaseStrategy(ABC):
    """Every strategy must inherit from this class."""
    def __init__(self, name: str, symbols: List[str], config: dict):
        self.name = name
        self.symbols = symbols
        self.config = config
        self._enabled = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    def enable(self):
        self._enabled = True

    def disable(self):
        self._enabled = False

    @abstractmethod
    async def on_tick(self, market_data: dict) -> List[Signal]:
        """
        Called periodically (e.g., every candle).
        market_data: dict with symbol -> latest OHLCV tick or order book.
        Return a list of generated signals.
        """
        ...