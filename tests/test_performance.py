import pytest
import asyncio
import time
from execution.order_executor import OrderExecutor
from models.trade_request import TradeRequest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_concurrent_order_latency(mock_exchange):
    executor = OrderExecutor(mock_exchange, ":memory:")
    # Simulate 50 concurrent orders
    reqs = [TradeRequest(symbol="BTCUSDT", side="buy", quantity=0.01, leverage=1) for _ in range(50)]
    mock_exchange.create_order = AsyncMock(return_value={"id": "1", "filled": 0.01, "average": 50000})
    start = time.monotonic()
    results = await executor.execute_orders(reqs)
    elapsed = time.monotonic() - start
    assert len(results) == 50
    # All orders should complete within reasonable time (depends on mock, but should be sub-second)
    assert elapsed < 2.0, f"Too slow: {elapsed:.2f}s"
    assert all(r.success for r in results)