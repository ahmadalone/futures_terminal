"""
Portfolio‑level simulation: runs multiple strategies concurrently with capital allocation.
"""
import asyncio
from typing import List, Dict
from backtesting.engine import BacktestEngine
from backtesting.data_loader import DataLoader
from models.backtest_result import BacktestResult
from execution.portfolio_allocator import PortfolioAllocator
from utils.logger import setup_logger

logger = setup_logger(__name__)

class PortfolioSimulator:
    def __init__(self, engine: BacktestEngine, data_loader: DataLoader):
        self.engine = engine
        self.data_loader = data_loader

    async def run(
        self,
        strategies: List[BaseStrategy],  # already instantiated with symbols
        allocation_pct: Dict[str, float],  # strategy_name -> fraction
        timeframe: str = "5m",
        start: datetime = None,
        end: datetime = None,
    ) -> Dict[str, BacktestResult]:
        """
        Run each strategy on its symbols and aggregate equity curves.
        """
        results = {}
        tasks = []
        for strat in strategies:
            # Run strategy on its primary symbol (first in list)
            symbol = strat.symbols[0] if strat.symbols else "BTCUSDT"
            task = self.engine.run(strat, symbol, timeframe, start, end, self.data_loader)
            tasks.append(task)

        strat_results = await asyncio.gather(*tasks)
        for strat, res in zip(strategies, strat_results):
            results[strat.name] = res
        # Aggregate equity: simple sum of equities (assuming no cross‑margin)
        # More sophisticated: rebalance based on allocation_pct
        return results