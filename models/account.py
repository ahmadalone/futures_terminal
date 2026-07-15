from pydantic import BaseModel, Field
from typing import Dict
from datetime import datetime

class AccountSnapshot(BaseModel):
    total_equity: float
    available_margin: float
    used_margin: float
    position_count: int = 0
    open_orders_count: int = 0
    balances: Dict[str, float] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)