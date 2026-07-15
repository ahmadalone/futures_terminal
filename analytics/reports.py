"""
Generate daily and monthly aggregated reports.
"""
import pandas as pd
from typing import List
from datetime import date
from models.analytics_report import DailyReport, MonthlyReport
from analytics.trade_journal import TradeJournal
from analytics.equity_curve import EquityCurve
from utils.logger import setup_logger

logger = setup_logger(__name__)

class ReportGenerator:
    def __init__(self, trade_journal: TradeJournal, equity_curve: EquityCurve):
        self.journal = trade_journal
        self.equity = equity_curve

    async def daily_report(self, target_date: date) -> DailyReport:
        trades = await self.journal.get_trades_df(start_date=target_date, end_date=target_date)
        pnl = 0.0
        # Get daily PnL from equity curve
        daily_pnl = await self.equity.get_daily_pnl()
        if target_date in daily_pnl.index:
            pnl = daily_pnl.loc[target_date]
        win_rate = (trades['price'].notna()).mean() if not trades.empty else 0  # placeholder
        return DailyReport(date=target_date, pnl=pnl, trades=len(trades), win_rate=win_rate)

    async def monthly_report(self, year: int, month: int) -> MonthlyReport:
        start = date(year, month, 1)
        end = date(year, month + 1, 1) if month < 12 else date(year+1, 1, 1)
        trades = await self.journal.get_trades_df(start_date=start, end_date=end)
        daily_pnl = await self.equity.get_daily_pnl()
        mask = (daily_pnl.index >= pd.Timestamp(start)) & (daily_pnl.index < pd.Timestamp(end))
        month_pnl = daily_pnl[mask].sum()
        best = daily_pnl[mask].max() if not daily_pnl[mask].empty else 0
        worst = daily_pnl[mask].min() if not daily_pnl[mask].empty else 0
        win_rate = (daily_pnl[mask] > 0).mean() if not daily_pnl[mask].empty else 0
        return MonthlyReport(
            month=f"{year}-{month:02d}",
            pnl=month_pnl,
            trades=len(trades),
            win_rate=win_rate,
            best_day=best,
            worst_day=worst
        )