import pytest
from strategies.base import BaseStrategy
from strategies.loader import StrategyLoader
from models.signal import Signal
from unittest.mock import AsyncMock
import tempfile, os, sys
from pathlib import Path

def test_strategy_loader_imports(tmp_path):
    # Create a dummy strategy file
    d = tmp_path / "strategies"
    d.mkdir()
    (d / "dummy.py").write_text("""
from strategies.base import BaseStrategy
from models.signal import Signal

class Dummy(BaseStrategy):
    async def on_tick(self, market_data):
        return [Signal(symbol='BTC', direction='long', strategy_name=self.name)]
""")
    loader = StrategyLoader(str(d))
    assert "Dummy" in loader.registry

def test_strategy_base_abstract():
    # Cannot instantiate abstract class
    with pytest.raises(TypeError):
        BaseStrategy("test", [], {})