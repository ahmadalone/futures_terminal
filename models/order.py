from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

class Order(BaseModel):
    """Represents an exchange order in a unified format."""
    id: str
    symbol: str
    type: Literal["market", "limit", "stop_market", "stop_limit", "trailing_stop", "take_profit", "take_profit_limit"]
    side: Literal["buy", "sell"]
    price: Optional[float] = None
    amount: float
    filled: float = 0.0
    remaining: float = 0.0
    status: Literal["open", "closed", "canceled", "expired", "rejected"] = "open"
    reduce_only: bool = False
    client_order_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    last_update: datetime = Field(default_factory=datetime.utcnow)