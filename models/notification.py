from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

class NotificationMessage(BaseModel):
    title: str
    body: str
    level: Literal["info", "warning", "critical"] = "info"
    category: Literal["trade", "risk", "daily_report", "system"] = "system"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict = Field(default_factory=dict)