from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

class Position(BaseModel):
    """Unified position model with extended risk metrics."""
    symbol: str
    side: Literal["long", "short"]
    quantity: float
    entry_price: float
    mark_price: float
    liquidation_price: Optional[float] = None
    leverage: int = 1
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    margin: float = 0.0
    notional: float = 0.0
    roe: float = 0.0
    # Additional risk/performance fields
    break_even_price: Optional[float] = None
    margin_ratio: Optional[float] = None         # maintenance margin %
    funding_rate: Optional[float] = None
    funding_fee: Optional[float] = None
    liquidation_distance_pct: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    last_update: datetime = Field(default_factory=datetime.utcnow)