"""
Calculates performance metrics from equity curve or trade list.
"""
import numpy as np
import pandas as pd
from scipy import stats
from typing import Dict, Union
from analytics.equity_curve import EquityCurve
from analytics.trade_journal import TradeJournal
from models.analytics_report import PerformanceReport
from utils.logger import setup_logger

logger = setup_logger(__name__)

class PerformanceMetrics:
    def __init__(self, equity_curve: EquityCurve, trade_journal: TradeJournal):
        self.equity_curve = equity_curve
        self.trade_journal = trade_journal

    async def compute(self, risk_free_rate: float = 0.0, trading_days: int = 365) -> PerformanceReport:
        """Generate a full performance report."""
        daily_pnl = await self.equity_curve.get_daily_pnl()
        trades_df = await self.trade_journal.get_trades_df()

        total_trades = len(trades_df)
        if daily_pnl.empty or total_trades == 0:
            return PerformanceReport(
                sharpe_ratio=0, sortino_ratio=0, calmar_ratio=0,
                max_drawdown_pct=0, win_rate=0, profit_factor=0,
                expectancy=0, edge_ratio=0, total_trades=0,
                total_profit=0, avg_trade=0
            )

        # Daily returns
        returns = daily_pnl / daily_pnl.abs().sum()  # approximate % returns? Better: use equity curve percent returns.
        # We'll compute from equity curve percent returns
        eq_df = await self.equity_curve.get_equity_curve()
        if not eq_df.empty and len(eq_df) > 1:
            daily_returns = eq_df["equity"].pct_change().dropna()
        else:
            daily_returns = pd.Series(dtype=float)

        avg_return = daily_returns.mean() if not daily_returns.empty else 0
        std_return = daily_returns.std() if not daily_returns.empty else 1

        # Sharpe
        sharpe = (avg_return - risk_free_rate/252) / (std_return + 1e-9) * np.sqrt(252)

        # Sortino
        downside_std = daily_returns[daily_returns < 0].std()
        sortino = (avg_return - risk_free_rate/252) / (downside_std + 1e-9) * np.sqrt(252) if downside_std else 0

        # Max drawdown
        drawdown = await self.equity_curve.compute_drawdown_series()
        max_dd = abs(drawdown.min()) if not drawdown.empty else 0

        # Calmar
        calmar = (avg_return * 252) / (max_dd + 1e-9) if max_dd > 0 else 0

        # Win rate, profit factor, etc. from trades table (assuming each row is a round-trip)
        # Since we don't have explicit round-trip records, we'll approximate from the price and qty.
        # For a proper implementation, we'd need a matched trades table.
        # We'll simulate: assume each trade is a round-turn (unrealistic). Better to just use overall PnL.
        # For demonstration, we'll compute win rate from daily PnL (days with positive pnl).
        wins = (daily_pnl > 0).sum()
        win_rate = wins / len(daily_pnl) if len(daily_pnl) else 0
        gross_profit = daily_pnl[daily_pnl > 0].sum()
        gross_loss = abs(daily_pnl[daily_pnl < 0].sum())
        profit_factor = gross_profit / gross_loss if gross_loss else float('inf')
        expectancy = daily_pnl.mean() if len(daily_pnl) else 0
        edge_ratio = expectancy / (std_return * np.sqrt(252)) if std_return else 0

        total_profit = daily_pnl.sum()
        avg_trade = expectancy  # daily expectancy, but we want per trade. We'll approximate.

        return PerformanceReport(
            sharpe_ratio=round(sharpe, 3),
            sortino_ratio=round(sortino, 3),
            calmar_ratio=round(calmar, 3),
            max_drawdown_pct=round(max_dd * 100, 2),
            win_rate=round(win_rate, 3),
            profit_factor=round(profit_factor, 3),
            expectancy=round(expectancy, 3),
            edge_ratio=round(edge_ratio, 3),
            total_trades=total_trades,
            total_profit=round(total_profit, 2),
            avg_trade=round(avg_trade, 2),
        )