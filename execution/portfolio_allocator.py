"""
Distributes capital among strategies based on equal weight or Kelly criterion.
"""
from models.signal import Signal
from utils.logger import setup_logger

logger = setup_logger(__name__)

class PortfolioAllocator:
    def __init__(self, config: dict):
        self.method = config.get("method", "equal")
        self.max_allocation_pct = config.get("max_allocation_pct", 20)  # % of equity per signal
        # For Kelly, we need trade history; simplified here.

    async def allocate(self, signal: Signal, total_equity: float) -> float:
        """
        Return the USDT amount to allocate for this signal.
        (Not quantity – the SignalExecutor will convert to contracts using price.)
        """
        if total_equity <= 0:
            return 0.0
        if self.method == "equal":
            # Divide equity equally among all active signals (assume all signals arrive at once)
            # For simplicity, each signal gets max_allocation_pct of equity.
            allocation = total_equity * (self.max_allocation_pct / 100.0)
            return min(allocation, total_equity * 0.2)  # cap at 20% of equity
        elif self.method == "kelly":
            # Placeholder: use fixed fraction
            fraction = 0.1  # 10% of Kelly-derived
            return total_equity * fraction
        return 0.0