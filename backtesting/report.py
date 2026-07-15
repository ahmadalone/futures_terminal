"""
Generate a comprehensive backtest report from a BacktestResult.
"""
from models.backtest_result import BacktestResult
from analytics.performance import PerformanceMetrics
from analytics.equity_curve import EquityCurve
from analytics.trade_journal import TradeJournal
import pandas as pd

async def generate_report(result: BacktestResult) -> PerformanceMetrics:
    """
    Reuse the analytics module to produce a performance report.
    (Already done inside engine, but can be used standalone.)
    """
    eq_df = pd.DataFrame(result.equity_curve).set_index("timestamp")
    eq_df.columns = ["equity"]
    ec = EquityCurve(":memory:")
    # Monkey-patch methods to use the provided data
    ec.get_equity_curve = lambda start=None, end=None: eq_df
    ec.get_daily_pnl = lambda: eq_df["equity"].resample("D").last().diff().dropna()
    tj = TradeJournal(":memory:")
    # We don't have individual trades here; skip for now.
    pm = PerformanceMetrics(ec, tj)
    return await pm.compute()