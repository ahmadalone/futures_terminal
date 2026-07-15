"""
Monte Carlo simulation – reshuffles trade PnL sequences.
"""
import asyncio
import numpy as np
from typing import List
from models.backtest_result import BacktestResult
from utils.logger import setup_logger

logger = setup_logger(__name__)

class MonteCarloSimulator:
    def __init__(self):
        pass

    async def simulate(
        self,
        base_result: BacktestResult,
        num_simulations: int = 1000,
    ) -> List[float]:
        """
        Given a base backtest result, resample trade PnL with replacement
        and compute final equity distribution. Returns list of final equities.
        """
        if not base_result.equity_curve:
            return []
        # Extract daily returns from equity curve
        import pandas as pd
        eq_df = pd.DataFrame(base_result.equity_curve).set_index("timestamp")
        eq_df.columns = ["equity"]
        returns = eq_df["equity"].pct_change().dropna().values
        if len(returns) == 0:
            return []
        initial = base_result.final_equity / (1 + returns.sum())  # approx
        final_equities = []
        for _ in range(num_simulations):
            sample = np.random.choice(returns, size=len(returns), replace=True)
            final = initial * (1 + sample.cumsum()[-1])
            final_equities.append(final)
        return final_equities

    async def confidence_interval(self, final_equities: List[float], ci: float = 0.95):
        """Return lower and upper bounds."""
        lower = np.percentile(final_equities, (1 - ci) / 2 * 100)
        upper = np.percentile(final_equities, (1 + ci) / 2 * 100)
        return lower, upper