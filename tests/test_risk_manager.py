import pytest
from execution.risk_manager import RiskManager
from models.trade_request import TradeRequest
from utils.config import AppConfig
from unittest.mock import AsyncMock, patch
from models.position import Position

@pytest.fixture
def risk_mgr(mock_exchange):
    config = AppConfig()
    position_mgr = AsyncMock()
    return RiskManager(config, mock_exchange, position_mgr, ":memory:")

@pytest.mark.asyncio
async def test_validate_batch_allowed(risk_mgr, mock_exchange):
    mock_exchange.fetch_ticker = AsyncMock(return_value={"last": 50000})
    position_mgr = risk_mgr.position_mgr
    position_mgr.get_open_positions = AsyncMock(return_value=[])
    req = TradeRequest(symbol="BTCUSDT", side="buy", usd_amount=100, leverage=1)
    allowed, reason = await risk_mgr.validate_batch([req], 10000)
    assert allowed
    assert reason == "OK"

@pytest.mark.asyncio
async def test_daily_loss_limit(risk_mgr, mock_exchange):
    risk_mgr.risk_config.max_daily_loss_usd = 500
    # Manually set daily PnL below limit
    risk_mgr._state.daily_pnl.net_pnl = -600
    allowed, reason = await risk_mgr.validate_batch([], 10000)
    assert not allowed
    assert "Daily loss limit exceeded" in reason

@pytest.mark.asyncio
async def test_circuit_breaker(risk_mgr):
    risk_mgr.risk_config.circuit_breaker.max_consecutive_failures = 2
    await risk_mgr.record_trade_result(success=False)
    await risk_mgr.record_trade_result(success=False)
    assert risk_mgr._state.circuit_breaker.triggered
    allowed, reason = await risk_mgr.validate_batch([], 10000)
    assert not allowed