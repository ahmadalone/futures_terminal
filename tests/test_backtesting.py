import pytest
import pandas as pd
from datetime import datetime
from backtesting.engine import BacktestEngine
from backtesting.data_loader import DataLoader
from models.signal import Signal
from strategies.base import BaseStrategy
from unittest.mock import AsyncMock, patch

class DummyStrategy(BaseStrategy):
    async def on_tick(self, market_data):
        # Buy at first tick and hold
        if not hasattr(self, '_fired'):
            self._fired = True
            return [Signal(symbol="BTCUSDT", direction="long", strength=1.0, confidence=1.0, strategy_name=self.name)]
        return []

@pytest.mark.asyncio
async def test_backtest_engine(tmp_path):
    # Create a mock DataLoader that returns historical data
    dates = pd.date_range("2023-01-01", periods=100, freq="5T")
    df = pd.DataFrame({
        "open": 100, "high": 102, "low": 99, "close": 101, "volume": 100
    }, index=dates)
    loader = AsyncMock()
    loader.load_ohlcv = AsyncMock(return_value=df)
    engine = BacktestEngine(initial_equity=10000)
    result = await engine.run(DummyStrategy("test", ["BTCUSDT"], {}), "BTCUSDT", start=datetime(2023,1,1), end=datetime(2023,1,2), data_loader=loader)
    assert result.trades > 0
    assert result.final_equity > 10000  # profit
    assert result.performance.sharpe_ratio != 0