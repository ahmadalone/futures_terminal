from pydantic import BaseModel, Field, PositiveFloat, PositiveInt, field_validator
from typing import Optional, Literal
from datetime import datetime

SizingMode = Literal["fixed_usdt", "percent_equity", "fixed_qty", "risk_based", "atr_based"]

class TradeRequest(BaseModel):
    symbol: str
    side: Literal["buy", "sell"]
    order_type: Literal["market", "limit", "stop_market", "stop_limit", "trailing_stop"] = "market"
    quantity: Optional[PositiveFloat] = None
    price: Optional[PositiveFloat] = None          # limit price
    stop_price: Optional[PositiveFloat] = None     # trigger price
    trailing_delta: Optional[PositiveFloat] = None # for trailing stop
    usd_amount: Optional[PositiveFloat] = None     # used for fixed_usdt / risk_based
    leverage: PositiveInt = 1
    reduce_only: bool = False
    stop_loss_pct: Optional[float] = None          # for risk‑based sizing
    take_profit_pct: Optional[float] = None        # not executed here, stored for later TP
    client_order_id: Optional[str] = None
    sizing_mode: SizingMode = "fixed_usdt"
    atr_period: PositiveInt = 14                   # for ATR sizing
    atr_multiplier: float = 2.0                    # stop distance multiplier (for ATR sizing)
    margin_mode: Literal["isolated", "cross"] = "isolated"
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("trailing_delta", mode="before")
    def check_trailing_stop(cls, v, info):
        if info.data.get("order_type") == "trailing_stop" and v is None:
            raise ValueError("trailing_delta required for trailing_stop orders")
        return v