"""
Fetches historical OHLCV data from exchange or local cache.
"""
import os
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List
import ccxt.async_support as ccxt
from utils.logger import setup_logger

logger = setup_logger(__name__)

class DataLoader:
    def __init__(self, cache_dir: str = "data/historical"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.exchange = ccxt.binance()  # could be configurable

    async def load_ohlcv(self, symbol: str, timeframe: str = "5m",
                         since: Optional[datetime] = None, limit: int = 1000) -> pd.DataFrame:
        """
        Fetch OHLCV from exchange or cache. Returns DataFrame with standard columns.
        """
        cache_file = self.cache_dir / f"{symbol}_{timeframe}_{since.strftime('%Y%m%d') if since else 'full'}.parquet"
        if cache_file.exists():
            logger.debug(f"Loading from cache {cache_file}")
            return pd.read_parquet(cache_file)

        since_ts = int(since.timestamp() * 1000) if since else None
        all_candles = []
        while True:
            candles = await self.exchange.fetch_ohlcv(symbol, timeframe, since=since_ts, limit=limit)
            if not candles:
                break
            all_candles.extend(candles)
            if len(candles) < limit:
                break
            since_ts = candles[-1][0] + 1
        if not all_candles:
            return pd.DataFrame()
        df = pd.DataFrame(all_candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
        df.to_parquet(cache_file)
        return df

    async def close(self):
        await self.exchange.close()