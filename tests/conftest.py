import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_exchange():
    """Create a mock BinanceFuturesClient with async methods."""
    mock = MagicMock()
    mock.load_markets = AsyncMock()
    mock.fetch_ticker = AsyncMock(return_value={"last": 50000.0, "bid": 49990, "ask": 50010})
    mock.fetch_balance = AsyncMock(return_value={"total": {"USDT": 10000.0}, "USDT": {"used": 0, "free": 10000, "total": 10000}})
    mock.fetch_positions = AsyncMock(return_value=[])
    mock.fetch_open_orders = AsyncMock(return_value=[])
    mock.create_order = AsyncMock(return_value={"id": "123", "filled": 0.1, "average": 50000, "price": 50000})
    mock.set_leverage = AsyncMock()
    mock.set_margin_mode = AsyncMock()
    mock.cancel_order = AsyncMock()
    mock.cancel_all_orders = AsyncMock()
    mock.exchange = MagicMock()
    mock.exchange.markets = {"BTCUSDT": {"swap": True, "linear": True, "quote": "USDT", "active": True}}
    return mock

@pytest.fixture
def config():
    from utils.config import AppConfig
    return AppConfig()

@pytest.fixture
def mock_db(tmp_path):
    import aiosqlite
    db_path = str(tmp_path / "test.db")
    # return path, not the actual db object
    return db_path