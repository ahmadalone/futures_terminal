import pytest
from execution.order_executor import OrderExecutor
from models.trade_request import TradeRequest
from unittest.mock import AsyncMock

@pytest.fixture
def executor(mock_exchange):
    return OrderExecutor(mock_exchange, ":memory:")

@pytest.mark.asyncio
async def test_execute_market_order(executor, mock_exchange):
    req = TradeRequest(symbol="BTCUSDT", side="buy", quantity=0.1, leverage=1)
    results = await executor.execute_orders([req])
    assert len(results) == 1
    assert results[0].success
    assert results[0].filled_quantity == 0.1

@pytest.mark.asyncio
async def test_execute_multiple_orders_concurrently(executor, mock_exchange):
    reqs = [
        TradeRequest(symbol="BTCUSDT", side="buy", quantity=0.1, leverage=1),
        TradeRequest(symbol="ETHUSDT", side="sell", quantity=1.0, leverage=2),
    ]
    results = await executor.execute_orders(reqs)
    assert len(results) == 2
    assert all(r.success for r in results)

@pytest.mark.asyncio
async def test_execute_retry_on_failure(executor, mock_exchange):
    mock_exchange.create_order = AsyncMock(side_effect=[
        Exception("timeout"),
        {"id": "456", "filled": 0.1, "average": 50000, "price": 50000}
    ])
    req = TradeRequest(symbol="BTCUSDT", side="buy", quantity=0.1, leverage=1)
    results = await executor.execute_orders([req])
    assert results[0].success
    assert results[0].order_id == "456"