"""
Constructs equity curve from account snapshots or trade P&L.
"""
import aiosqlite
import pandas as pd
from datetime import date, datetime
from typing import Optional, List
from utils.logger import setup_logger

logger = setup_logger(__name__)

class EquityCurve:
    def __init__(self, db_path: str = "trading_terminal.db"):
        self.db_path = db_path

    async def get_equity_curve(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> pd.DataFrame:
        """Fetch account snapshots and build equity series."""
        async with aiosqlite.connect(self.db_path) as db:
            query = "SELECT ts, total_equity FROM account_snapshots ORDER BY ts ASC"
            params = []
            if start_date:
                query = "SELECT ts, total_equity FROM account_snapshots WHERE ts >= ? ORDER BY ts ASC"
                params = [start_date.isoformat()]
            rows = await db.execute_fetchall(query, params)
            if not rows:
                return pd.DataFrame(columns=["ts", "equity"])
            data = [{"ts": datetime.fromisoformat(r[0]), "equity": r[1]} for r in rows]
            df = pd.DataFrame(data).set_index("ts")
            if end_date:
                df = df[df.index <= pd.Timestamp(end_date)]
            return df

    async def get_daily_pnl(self) -> pd.Series:
        """Compute daily PnL from account snapshots (if available)."""
        df = await self.get_equity_curve()
        if df.empty:
            return pd.Series(dtype=float)
        daily_equity = df["equity"].resample("D").last()
        daily_pnl = daily_equity.diff().dropna()
        return daily_pnl

    async def compute_drawdown_series(self) -> pd.Series:
        """Return drawdown percentage series."""
        eq = await self.get_equity_curve()
        if eq.empty:
            return pd.Series(dtype=float)
        rolling_max = eq["equity"].cummax()
        drawdown = (eq["equity"] - rolling_max) / rolling_max
        return drawdown