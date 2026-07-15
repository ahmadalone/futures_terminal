"""
Example plugin: Moving Average Crossover strategy.
"""
from typing import List
import numpy as np
from models.signal import Signal
from plugins.base import PluginBase
from utils.logger import setup_logger

class MACrossoverPlugin(PluginBase):
    """
    Generates a long signal when short MA crosses above long MA,
    and a short signal when short MA crosses below long MA.
    """
    async def on_tick(self, market_data: dict) -> List[Signal]:
        signals = []
        # Parameters from manifest
        fast_period = self.manifest.parameters.get("fast_ma", 10)
        slow_period = self.manifest.parameters.get("slow_ma", 30)
        # We need historical OHLCV to compute MAs. For simplicity, we use a simple price list stored in the plugin.
        if not hasattr(self, '_price_history'):
            self._price_history = {}
        for sym in self.manifest.symbols:
            if sym not in market_data:
                continue
            price = market_data[sym].get("last")
            if price is None:
                continue
            # Keep last 100 prices
            if sym not in self._price_history:
                self._price_history[sym] = []
            self._price_history[sym].append(price)
            if len(self._price_history[sym]) > 100:
                self._price_history[sym].pop(0)
            if len(self._price_history[sym]) < slow_period + 1:
                continue
            prices = self._price_history[sym]
            # Compute fast and slow MA
            fast_ma = np.mean(prices[-int(fast_period):])
            slow_ma = np.mean(prices[-int(slow_period):])
            prev_fast = np.mean(prices[-int(fast_period)-1:-1])
            prev_slow = np.mean(prices[-int(slow_period)-1:-1])
            # Crossover detection
            if prev_fast <= prev_slow and fast_ma > slow_ma:
                signals.append(Signal(
                    symbol=sym,
                    direction="long",
                    strength=0.8,
                    confidence=0.7,
                    strategy_name=self.manifest.name,
                    metadata={"fast_ma": fast_ma, "slow_ma": slow_ma}
                ))
            elif prev_fast >= prev_slow and fast_ma < slow_ma:
                signals.append(Signal(
                    symbol=sym,
                    direction="short",
                    strength=0.8,
                    confidence=0.7,
                    strategy_name=self.manifest.name,
                    metadata={"fast_ma": fast_ma, "slow_ma": slow_ma}
                ))
        return signals