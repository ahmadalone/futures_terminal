"""Models for risk engine state."""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date

class DailyPnL(BaseModel):
    date: date
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    net_pnl: float = 0.0

class EquityCurve(BaseModel):
    timestamp: datetime
    equity: float

class CircuitBreakerState(BaseModel):
    triggered: bool = False
    reason: Optional[str] = None
    consecutive_failures: int = 0
    last_reset: datetime = Field(default_factory=datetime.utcnow)

class RiskState(BaseModel):
    """Holds dynamic risk state loaded at start and updated in memory."""
    daily_pnl: DailyPnL = Field(default_factory=lambda: DailyPnL(date=date.today()))
    peak_equity: float = 0.0
    current_drawdown_pct: float = 0.0
    circuit_breaker: CircuitBreakerState = Field(default_factory=CircuitBreakerState)
    trading_paused: bool = False   # can be set externally (news)
    pause_reason: Optional[str] = None