import pytest
from execution.position_manager import PositionManager
from models.position import Position
from unittest.mock import AsyncMock

@pytest.fixture
def position_mgr(mock_exchange):
    executor = AsyncMock()
    return PositionManager(mock_exchange, executor, ":memory:")

@pytest.mark.asyncio
async def test_get_open_positions_empty(position_mgr, mock_exchange):
    positions = await position_mgr.get_open_positions()
    assert len(positions) == 0

@pytest.mark.asyncio
async def test_get_open_positions(position_mgr, mock_exchange):
    mock_exchange.fetch_positions = AsyncMock(return_value=[
        {"symbol": "BTCUSDT", "contracts": 0.1, "entryPrice": 48000, "markPrice": 50000,
         "unrealizedPnl": 200, "leverage": 5, "liquidationPrice": 40000, "initialMargin": 960,
         "notional": 5000}
    ])
    positions = await position_mgr.get_open_positions()
    assert len(positions) == 1
    assert positions[0].symbol == "BTCUSDT"
    assert positions[0].unrealized_pnl == 200

@pytest.mark.asyncio
async def test_emergency_close_all(position_mgr, mock_exchange):
    mock_exchange.fetch_positions = AsyncMock(return_value=[
        {"symbol": "BTCUSDT", "contracts": 0.1, "entryPrice": 48000, "markPrice": 50000,
         "unrealizedPnl": 200, "leverage": 5, "liquidationPrice": 40000, "initialMargin": 960,
         "notional": 5000},
        {"symbol": "ETHUSDT", "contracts": -0.5, "entryPrice": 3000, "markPrice": 2900,
         "unrealizedPnl": -50, "leverage": 10, "liquidationPrice": 3500, "initialMargin": 150,
         "notional": 1450}
    ])
    mock_exchange.create_order = AsyncMock(return_value={"id": "999", "filled": 0.1, "average": 50000})
    position_mgr.executor.execute_orders = AsyncMock(return_value=[TradeResult(symbol="BTCUSDT", success=True, message="closed")])
    results = await position_mgr.emergency_close_all()
    assert len(results) == 2  # mocked call returns 2 results