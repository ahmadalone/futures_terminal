"""
Walk‑forward testing: split data into in‑sample and out‑of‑sample windows.
"""
import asyncio
from datetime import datetime, timedelta
from typing import List
from backtesting.engine import BacktestEngine
from backtesting.data_loader import DataLoader
from models.backtest_result import BacktestResult
from strategies.base import BaseStrategy
from utils.logger import setup_logger

logger = setup_logger(__name__)

class WalkForwardTester:
    def __init__(self, engine: BacktestEngine, data_loader: DataLoader):
        self.engine = engine
        self.data_loader = data_loader

    async def run(
        self,
        strategy_class,  # not instance, we instantiate for each window
        symbol: str,
        timeframe: str = "5m",
        start: datetime = None,
        end: datetime = None,
        window_size_days: int = 30,
        step_days: int = 7,
        params: dict = None,
    ) -> List[BacktestResult]:
        """
        Perform walk‑forward analysis.
        Returns list of BacktestResult for each OOS window.
        """
        results = []
        current_start = start
        while current_start < end:
            train_start = current_start
            train_end = train_start + timedelta(days=window_size_days)
            test_start = train_end
            test_end = min(test_start + timedelta(days=step_days), end)
            if test_start >= end:
                break

            # Train the strategy on in‑sample (simulate with same engine)
            strategy_ins = strategy_class(name=f"{strategy_class.__name__}_IS", symbols=[symbol], config=params or {})
            ins_result = await self.engine.run(strategy_ins, symbol, timeframe, train_start, train_end, self.data_loader)
            # For simplicity, we don't do parameter updating; just run OOS with same params
            strategy_oos = strategy_class(name=f"{strategy_class.__name__}_OOS", symbols=[symbol], config=params or {})
            oos_result = await self.engine.run(strategy_oos, symbol, timeframe, test_start, test_end, self.data_loader)
            oos_result.parameters["train_period"] = f"{train_start.date()} - {train_end.date()}"
            results.append(oos_result)

            current_start += timedelta(days=step_days)
        return results