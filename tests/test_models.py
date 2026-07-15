import pytest
from pydantic import ValidationError
from models.trade_request import TradeRequest
from models.trade_result import TradeResult
from models.signal import Signal

def test_trade_request_valid():
    req = TradeRequest(symbol="BTCUSDT", side="buy", usd_amount=100, leverage=5)
    assert req.symbol == "BTCUSDT"

def test_trade_request_invalid_side():
    with pytest.raises(ValidationError):
        TradeRequest(symbol="BTCUSDT", side="invalid")

def test_signal_defaults():
    sig = Signal(symbol="ETHUSDT", direction="long", strategy_name="test")
    assert sig.confidence == 0.5

def test_trade_result_success():
    res = TradeResult(symbol="BTC", success=True, message="filled")
    assert res.success