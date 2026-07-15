from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime
from analytics.performance import PerformanceReport

class BacktestResult(BaseModel):
    symbol: str
    strategy: str
    start_date: datetime
    end_date: datetime
    trades: int
    final_equity: float
    performance: PerformanceReport
    equity_curve: List[Dict] = Field(default_factory=list)  # list of {timestamp, equity}
    parameters: Dict = Field(default_factory=dict)

class OptimizationResult(BaseModel):
    best_params: Dict
    best_score: float
    all_results: List[Dict]  # list of param sets and scores