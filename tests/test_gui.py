import pytest
import sys
from PySide6.QtWidgets import QApplication

pytestmark = pytest.mark.gui

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app

def test_watchlist_widget(qapp, mock_exchange):
    from gui.widgets.watchlist import WatchlistWidget
    widget = WatchlistWidget()
    widget.populate(["BTCUSDT", "ETHUSDT"])
    assert widget.list.count() == 2

def test_trade_panel_defaults(qapp):
    from gui.widgets.trade_panel import TradePanel
    panel = TradePanel()
    req = panel.get_trade_request()
    assert req.leverage == 10

def test_positions_table(qapp):
    from gui.widgets.positions_table import PositionsTable
    tbl = PositionsTable()
    tbl.update_positions([{"symbol": "BTCUSDT", "side": "long", "quantity": 0.1, "entry_price": 50000, "mark_price": 51000, "unrealized_pnl": 100, "liquidation_price": 40000}])
    assert tbl.table.rowCount() == 1