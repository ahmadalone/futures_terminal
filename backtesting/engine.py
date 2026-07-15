"""
Core backtesting engine – simulates a single strategy on one symbol.
"""
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from typing import Optional, Callable, List, Dict
from models.trade_request import TradeRequest
from models.trade_result import TradeResult
from models.signal import Signal
from strategies.base import BaseStrategy
from execution.portfolio_allocator import PortfolioAllocator
from analytics.equity_curve import EquityCurve
from analytics.performance import PerformanceMetrics
from backtesting.data_loader import DataLoader
from models.backtest_result import BacktestResult
from utils.logger import setup_logger

logger = setup_logger(__name__)

class BacktestEngine:
    """
    Runs a single strategy over historical data and simulates fills.
    """
    def __init__(self, initial_equity: float = 10000, fee_rate: float = 0.0004, slippage_pct: float = 0.0005):
        self.initial_equity = initial_equity
        self.fee_rate = fee_rate
        self.slippage_pct = slippage_pct

    async def run(
        self,
        strategy: BaseStrategy,
        symbol: str,
        timeframe: str = "5m",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        data_loader: DataLoader = None,
    ) -> BacktestResult:
        """
        Execute the strategy on historical data.
        Returns a BacktestResult with full equity curve and performance.
        """
        if data_loader is None:
            data_loader = DataLoader()
        df = await data_loader.load_ohlcv(symbol, timeframe, since=start, limit=2000)
        if start:
            df = df[df.index >= start]
        if end:
            df = df[df.index <= end]
        if df.empty:
            raise ValueError("No historical data for the specified period")

        # Prepare state
        equity = self.initial_equity
        position = 0.0       # + long, - short
        entry_price = 0.0
        trades = []
        equity_curve = []
        signal_queue = []

        # Create a simple allocator (no risk manager for now)
        allocator = PortfolioAllocator({"method": "equal", "max_allocation_pct": 20})

        # Iterate through bars
        for idx, (ts, bar) in enumerate(df.iterrows()):
            # Build market data dict as expected by strategy
            market_data = {symbol: {
                "last": bar["close"],
                "high": bar["high"],
                "low": bar["low"],
                "open": bar["open"],
                "volume": bar["volume"],
                "timestamp": ts
            }}

            # Get signals from strategy (only at every bar, not tick-level)
            if idx % 1 == 0:  # every bar
                try:
                    signals = await strategy.on_tick(market_data)
                    if signals:
                        signal_queue.extend(signals)
                except Exception as e:
                    logger.error(f"Strategy error at {ts}: {e}")

            # Process signals (simplified: take first signal per bar)
            if signal_queue:
                sig = signal_queue.pop(0)
                # Convert signal to trade
                side = "buy" if sig.direction == "long" else ("sell" if sig.direction == "short" else None)
                if side is None:
                    continue
                # Calculate quantity based on current equity and price
                qty = await self._calculate_qty(allocator, sig, equity, bar["close"])
                # Simulate execution
                fill_price = bar["close"] * (1 + self.slippage_pct) if side == "buy" else bar["close"] * (1 - self.slippage_pct)
                fee = qty * fill_price * self.fee_rate
                fill_volume = qty
                # Update position and equity
                if side == "buy":
                    if position < 0:
                        # close short
                        profit = (entry_price - fill_price) * abs(position) - fee
                        equity += profit
                        trades.append({"ts": ts, "symbol": symbol, "side": "close_short", "qty": abs(position), "price": fill_price, "pnl": profit})
                        position = 0
                    # open long
                    position += fill_volume
                    entry_price = fill_price
                    equity -= fee  # deduct fee
                    trades.append({"ts": ts, "symbol": symbol, "side": "buy", "qty": fill_volume, "price": fill_price, "pnl": 0})
                else:  # sell
                    if position > 0:
                        # close long
                        profit = (fill_price - entry_price) * position - fee
                        equity += profit
                        trades.append({"ts": ts, "symbol": symbol, "side": "close_long", "qty": position, "price": fill_price, "pnl": profit})
                        position = 0
                    # open short
                    position -= fill_volume
                    entry_price = fill_price
                    equity -= fee
                    trades.append({"ts": ts, "symbol": symbol, "side": "sell", "qty": fill_volume, "price": fill_price, "pnl": 0})

            # Mark-to-market equity (including unrealized PnL)
            if position != 0:
                if position > 0:
                    unrealized = (bar["close"] - entry_price) * position
                else:
                    unrealized = (entry_price - bar["close"]) * abs(position)
                mtm_equity = equity + unrealized
            else:
                mtm_equity = equity
            equity_curve.append({"timestamp": ts, "equity": mtm_equity})

        # Close any open position at the last price
        if position != 0:
            last_price = df.iloc[-1]["close"]
            if position > 0:
                profit = (last_price - entry_price) * position
            else:
                profit = (entry_price - last_price) * abs(position)
            equity += profit - (abs(position) * last_price * self.fee_rate)
            trades.append({"ts": df.index[-1], "symbol": symbol, "side": "close", "qty": abs(position), "price": last_price, "pnl": profit})
            position = 0
            equity_curve[-1]["equity"] = equity

        # Build performance report using analytics
        # Convert equity_curve to a DataFrame for analytics
        eq_df = pd.DataFrame(equity_curve).set_index("timestamp")
        eq_df.columns = ["equity"]
        # Create a temporary EquityCurve object with our data
        from analytics.equity_curve import EquityCurve
        ec = EquityCurve(":memory:")  # not used directly; we'll monkey-patch
        ec.get_equity_curve = lambda start=None, end=None: eq_df
        ec.get_daily_pnl = lambda: eq_df["equity"].resample("D").last().diff().dropna()
        # Also need a trade journal for PerformanceMetrics (will create dummy)
        from analytics.trade_journal import TradeJournal
        tj = TradeJournal(":memory:")
        # Build fake trades df
        trades_df = pd.DataFrame(trades)
        if not trades_df.empty:
            trades_df["ts"] = pd.to_datetime(trades_df["ts"])
            trades_df["date"] = trades_df["ts"].dt.date
        tj.get_trades_df = lambda start=None, end=None: trades_df if not trades_df.empty else pd.DataFrame()

        from analytics.performance import PerformanceMetrics
        pm = PerformanceMetrics(ec, tj)
        perf_report = await pm.compute()

        return BacktestResult(
            symbol=symbol,
            strategy=strategy.name,
            start_date=df.index[0],
            end_date=df.index[-1],
            trades=len(trades),
            final_equity=equity,
            performance=perf_report,
            equity_curve=equity_curve,
            parameters=getattr(strategy, 'config', {})
        )

    async def _calculate_qty(self, allocator, signal, equity, price):
        # Simple fixed percent of equity
        risk_capital = equity * 0.2  # 20%
        qty = risk_capital / price
        return qty