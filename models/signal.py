from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

class Signal(BaseModel):
    """Unified trading signal from a strategy."""
    symbol: str
    direction: Literal["long", "short", "close"]
    strength: float = Field(default=1.0, ge=0.0, le=1.0)  # 0.0 – 1.0
    confidence: float = Field(default=0.5, ge=0.0, le=1.0) # strategy confidence
    strategy_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict = Field(default_factory=dict)  # any extra info