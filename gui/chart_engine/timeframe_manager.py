"""
Fetches and caches OHLCV data for different timeframes.
"""
import asyncio
from typing import List, Optional
from exchange.futures_client import BinanceFuturesClient
from utils.logger import setup_logger

logger = setup_logger(__name__)

class TimeframeManager:
    def __init__(self, client: BinanceFuturesClient):
        self.client = client
        self.cache = {}

    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 200) -> Optional[List[List[float]]]:
        try:
            ohlcv = await self.client.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            processed = []
            for c in ohlcv:
                ts = c[0] / 1000.0
                processed.append([ts, c[1], c[2], c[3], c[4], c[5]])
            self.cache[(symbol, timeframe)] = processed
            return processed
        except Exception as e:
            logger.error(f"Fetch OHLCV failed: {e}")
            return self.cache.get((symbol, timeframe), [])