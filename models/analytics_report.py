from pydantic import BaseModel
from typing import List, Dict
from datetime import date

class PerformanceReport(BaseModel):
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown_pct: float
    win_rate: float
    profit_factor: float
    expectancy: float
    edge_ratio: float
    total_trades: int
    total_profit: float
    avg_trade: float

class DailyReport(BaseModel):
    date: date
    pnl: float
    trades: int
    win_rate: float

class MonthlyReport(BaseModel):
    month: str  # YYYY-MM
    pnl: float
    trades: int
    win_rate: float
    best_day: float
    worst_day: float

class HeatmapData(BaseModel):
    year: int
    days: Dict[date, float]  # date -> pnl