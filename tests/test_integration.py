import pytest
import os
from exchange.futures_client import BinanceFuturesClient
from execution.order_executor import OrderExecutor
from models.trade_request import TradeRequest

pytestmark = pytest.mark.integration

API_KEY = os.getenv("BINANCE_TESTNET_API_KEY")
SECRET = os.getenv("BINANCE_TESTNET_SECRET")

@pytest.mark.skipif(not (API_KEY and SECRET), reason="No testnet keys")
@pytest.mark.asyncio
async def test_fetch_ticker_integration():
    client = BinanceFuturesClient(API_KEY, SECRET, testnet=True)
    await client.load_markets()
    ticker = await client.fetch_ticker("BTCUSDT")
    assert ticker["last"] > 0
    await client.exchange.close()

@pytest.mark.skipif(not (API_KEY and SECRET), reason="No testnet keys")
@pytest.mark.asyncio
async def test_place_market_order():
    client = BinanceFuturesClient(API_KEY, SECRET, testnet=True)
    await client.load_markets()
    executor = OrderExecutor(client, ":memory:")
    req = TradeRequest(symbol="BTCUSDT", side="buy", quantity=0.001, leverage=1)  # small
    results = await executor.execute_orders([req])
    assert results[0].success
    await client.exchange.close()