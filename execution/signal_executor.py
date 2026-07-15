"""
Converts strategy signals into TradeRequests and executes them.
"""
from typing import List
from models.signal import Signal
from models.trade_request import TradeRequest
from execution.order_executor import OrderExecutor
from execution.risk_manager import RiskManager
from execution.portfolio_allocator import PortfolioAllocator
from utils.logger import setup_logger

logger = setup_logger(__name__)

class SignalExecutor:
    """Takes signals from strategies, allocates capital, and places orders."""
    def __init__(
        self,
        order_executor: OrderExecutor,
        risk_manager: RiskManager,
        allocator: PortfolioAllocator,
    ):
        self.executor = order_executor
        self.risk_mgr = risk_manager
        self.allocator = allocator

    async def execute_signals(self, signals: List[Signal], equity: float):
        """
        Convert signals to trade requests, validate risk, and execute.
        Returns list of TradeResults.
        """
        if not signals:
            return []
        # Aggregate signals per symbol/direction (simplified: take strongest)
        aggregated = {}
        for sig in signals:
            key = (sig.symbol, sig.direction)
            if key not in aggregated or sig.strength > aggregated[key].strength:
                aggregated[key] = sig

        # Build requests
        requests = []
        for sig in aggregated.values():
            # Determine quantity via portfolio allocator
            qty = await self.allocator.allocate(sig, equity)
            if qty <= 0:
                continue
            side = "buy" if sig.direction == "long" else ("sell" if sig.direction == "short" else None)
            if side is None:
                continue
            req = TradeRequest(
                symbol=sig.symbol,
                side=side,
                order_type="market",
                quantity=qty,
                leverage=1,  # could be overridden per strategy
                reduce_only=False,
                client_order_id=f"{sig.strategy_name}_{sig.timestamp.isoformat()}",
            )
            requests.append(req)

        # Validate risk
        positions = []  # fetch current positions if needed
        allowed, reason = await self.risk_mgr.validate_batch(requests, equity, positions)
        if not allowed:
            logger.warning(f"Risk validation failed: {reason}")
            return []

        # Execute
        results = await self.executor.execute_orders(requests)
        # Record trade results in risk manager
        for res in results:
            await self.risk_mgr.record_trade_result(res.success)
        return results