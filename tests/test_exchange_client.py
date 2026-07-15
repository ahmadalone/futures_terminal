import pytest
from unittest.mock import AsyncMock, patch
from exchange.futures_client import BinanceFuturesClient

@pytest.mark.asyncio
async def test_load_markets(mock_exchange):
    with patch('ccxt.pro.binance', return_value=mock_exchange.exchange):
        client = BinanceFuturesClient("key", "secret")
        client.exchange = mock_exchange
        await client.load_markets()
        assert client._markets_loaded

@pytest.mark.asyncio
async def test_fetch_ticker(mock_exchange):
    client = BinanceFuturesClient("key", "secret")
    client.exchange = mock_exchange
    client._markets_loaded = True
    ticker = await client.fetch_ticker("BTCUSDT")
    assert ticker["last"] == 50000.0

@pytest.mark.asyncio
async def test_create_order(mock_exchange):
    client = BinanceFuturesClient("key", "secret")
    client.exchange = mock_exchange
    client._markets_loaded = True
    order = await client.create_order("BTCUSDT", "market", "buy", 0.1)
    assert order["id"] == "123"