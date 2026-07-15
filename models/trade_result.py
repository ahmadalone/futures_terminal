from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class TradeResult(BaseModel):
    symbol: str
    order_id: Optional[str] = None
    success: bool
    message: str
    execution_timestamp: Optional[datetime] = None
    latency_submit_ms: Optional[float] = None
    latency_ack_ms: Optional[float] = None
    filled_quantity: Optional[float] = None
    avg_price: Optional[float] = None