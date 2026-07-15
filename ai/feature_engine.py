"""
Computes technical indicators for a given symbol and timeframe.
Returns a pandas DataFrame with features suitable for ML models.
"""
import asyncio
import numpy as np
import pandas as pd
from typing import List, Optional
from exchange.futures_client import BinanceFuturesClient
from utils.logger import setup_logger

logger = setup_logger(__name__)

class FeatureEngine:
    def __init__(self, client: BinanceFuturesClient):
        self.client = client

    async def compute_features(self, symbol: str, timeframe: str = "5m", lookback: int = 500) -> pd.DataFrame:
        """
        Fetch OHLCV and compute a rich feature set.
        Returns DataFrame with datetime index and feature columns.
        """
        raw = await self.client.exchange.fetch_ohlcv(symbol, timeframe, limit=lookback+50)
        if len(raw) == 0:
            raise ValueError(f"No OHLCV data for {symbol}")
        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)

        # Price features
        df["returns"] = df["close"].pct_change()
        df["log_returns"] = np.log(df["close"] / df["close"].shift(1))
        df["high_low_pct"] = (df["high"] - df["low"]) / df["close"]
        df["close_open_pct"] = (df["close"] - df["open"]) / df["open"]

        # Moving averages
        for window in [5, 10, 20, 50]:
            df[f"sma_{window}"] = df["close"].rolling(window).mean()
            df[f"ema_{window}"] = df["close"].ewm(span=window, adjust=False).mean()
            df[f"volatility_{window}"] = df["returns"].rolling(window).std()

        # RSI
        df["rsi_14"] = self._rsi(df["close"], 14)

        # MACD
        ema12 = df["close"].ewm(span=12, adjust=False).mean()
        ema26 = df["close"].ewm(span=26, adjust=False).mean()
        df["macd"] = ema12 - ema26
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]

        # Bollinger Bands
        sma20 = df["close"].rolling(20).mean()
        std20 = df["close"].rolling(20).std()
        df["bb_upper"] = sma20 + 2 * std20
        df["bb_lower"] = sma20 - 2 * std20
        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / sma20

        # ATR
        df["atr_14"] = self._atr(df, 14)

        # Volume features
        df["volume_sma_10"] = df["volume"].rolling(10).mean()
        df["volume_ratio"] = df["volume"] / df["volume_sma_10"]

        # Target: next bar direction (up/down) – will be used for training labels
        df["target"] = (df["close"].shift(-1) > df["close"]).astype(int)

        # Drop NaN
        df.dropna(inplace=True)
        return df

    @staticmethod
    def _rsi(series, period):
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(period).mean()
        avg_loss = loss.rolling(period).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    @staticmethod
    def _atr(df, period):
        high, low, close = df["high"], df["low"], df["close"]
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(period).mean()