"""
Loads trades from database and returns a pandas DataFrame for analysis.
"""
import aiosqlite
from datetime import datetime, date
from typing import Optional, List, Dict
import pandas as pd
from utils.logger import setup_logger

logger = setup_logger(__name__)

class TradeJournal:
    def __init__(self, db_path: str = "trading_terminal.db"):
        self.db_path = db_path

    async def get_trades_df(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> pd.DataFrame:
        """Return all trades from the database as a DataFrame."""
        async with aiosqlite.connect(self.db_path) as db:
            query = "SELECT * FROM trades WHERE success = 1"
            params = []
            if start_date:
                query += " AND ts >= ?"
                params.append(start_date.isoformat())
            if end_date:
                query += " AND ts <= ?"
                params.append(end_date.isoformat())
            rows = await db.execute_fetchall(query, params)
            columns = [desc[0] for desc in rows.description] if rows else []
            data = [dict(zip(columns, row)) for row in rows]
            df = pd.DataFrame(data)
            if not df.empty:
                df["ts"] = pd.to_datetime(df["ts"])
                df["date"] = df["ts"].dt.date
            return df

    async def get_closed_positions(self) -> pd.DataFrame:
        """Return only trades that appear to close a position (approximate)."""
        # Since our DB doesn't track position pairing, we aggregate buys and sells per symbol.
        df = await self.get_trades_df()
        if df.empty:
            return pd.DataFrame()
        # Simple matching: group by symbol and side, but we can treat each trade as a round-turn for metrics.
        # For proper closed P&L, we'd need to match buy/sell. For now, we use the price as a placeholder.
        # Actually, we can compute PnL from trades table itself? Not directly.
        # We'll rely on account snapshots for equity curve and performance.
        return df