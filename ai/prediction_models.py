from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Literal

class Prediction(BaseModel):
    symbol: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    direction: Literal["up", "down"]
    probability: float  # 0.0 – 1.0
    confidence: float   # 0.0 – 1.0, how reliable the model believes this is
    model_name: str
    metadata: dict = Field(default_factory=dict)