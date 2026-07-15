import asyncio
import logging
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QDockWidget, QVBoxLayout, QSplitter,
    QMessageBox, QApplication, QMenu, QTextEdit
)
from PySide6.QtCore import Qt, QTimer, QSettings
import qasync

from exchange.futures_client import BinanceFuturesClient
from execution.order_executor import OrderExecutor
from execution.position_manager import PositionManager
from execution.risk_manager import RiskManager
from utils.config import AppConfig
from models.trade_request import TradeRequest
from models.notification import NotificationMessage
from notifications.manager import NotificationManager
from gui.widgets.watchlist import WatchlistWidget
from gui.widgets.trade_panel import TradePanel
from gui.widgets.positions_table import PositionsTable
from gui.widgets.order_book import OrderBookWidget
from gui.widgets.recent_trades import RecentTradesWidget
from gui.widgets.account_balance import AccountBalanceWidget
from gui.widgets.risk_monitor import RiskMonitorWidget
from gui.widgets.log_widget import QTextEditLogger
from gui.chart_engine.chart_widget import ChartWidget
from gui.widgets.performance_dashboard import PerformanceDashboard
from gui.dark_theme import load_dark_theme

logger = logging.getLogger("gui")

class MainWindow(QMainWindow):
    def __init__(self, client: BinanceFuturesClient, executor: OrderExecutor,
                 position_mgr: PositionManager, risk_mgr: RiskManager,
                 config: AppConfig, nm: NotificationManager):
        super().__init__()
        self.client = client
        self.executor = executor
        self.position_mgr = position_mgr
        self.risk_mgr = risk_mgr
        self.config = config
        self.nm = nm
        self._selected_symbols = []
        self._market_tasks = []

        self.setWindowTitle("Futures Terminal - Professional")
        self.resize(1600, 900)
        self._settings = QSettings("FuturesTerminal", "MainWindow")

        self._init_ui()
        self._load_state()

        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._async_refresh)
        self.refresh_timer.start(500)

        self.watchlist.symbols_changed.connect(self._on_symbols_changed)
        self.trade_panel.execute_signal.connect(self._on_execute)
        self.positions_table.close_position_signal.connect(self._on_close_position)

        log_handler = QTextEditLogger(self.log_widget)
        logging.getLogger().addHandler(log_handler)
        logging.getLogger().setLevel(logging.INFO)

    def _init_ui(self):
        # Left dock: Watchlist + Trade Panel
        left_dock = QDockWidget("Watchlist & Trade", self)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        self.watchlist = WatchlistWidget()
        self.trade_panel = TradePanel()
        left_layout.addWidget(self.watchlist)
        left_layout.addWidget(self.trade_panel)
        left_dock.setWidget(left_widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, left_dock)

        # Right dock: Order Book, Trades, Account, Risk
        right_dock = QDockWidget("Market & Account", self)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        self.order_book = OrderBookWidget()
        self.recent_trades = RecentTradesWidget()
        self.account_balance = AccountBalanceWidget()
        self.risk_monitor = RiskMonitorWidget()
        right_layout.addWidget(self.order_book)
        right_layout.addWidget(self.recent_trades)
        right_layout.addWidget(self.account_balance)
        right_layout.addWidget(self.risk_monitor)
        right_dock.setWidget(right_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, right_dock)

        # Bottom dock: Logs & Performance
        bottom_dock = QDockWidget("Logs & Performance", self)
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        self.log_widget = QTextEdit()
        self.performance = PerformanceDashboard(self.config.database.path)
        bottom_layout.addWidget(self.log_widget)
        bottom_layout.addWidget(self.performance)
        bottom_dock.setWidget(bottom_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, bottom_dock)

        # Center: Chart + Positions
        self.chart = ChartWidget(self.client)
        self.positions_table = PositionsTable()
        center_splitter = QSplitter(Qt.Vertical)
        center_splitter.addWidget(self.chart)
        center_splitter.addWidget(self.positions_table)
        self.setCentralWidget(center_splitter)

        # Menu
        menubar = self.menuBar()
        view_menu = menubar.addMenu("View")
        for dock in self.findChildren(QDockWidget):
            view_menu.addAction(dock.toggleViewAction())

        self.statusBar().showMessage("Ready")

    def _start_streams(self):
        for t in self._market_tasks:
            t.cancel()
        self._market_tasks.clear()
        if not self._selected_symbols:
            return
        for sym in self._selected_symbols:
            self._market_tasks.append(asyncio.ensure_future(self._stream_order_book(sym)))
            self._market_tasks.append(asyncio.ensure_future(self._stream_trades(sym)))

    async def _stream_order_book(self, symbol):
        while True:
            try:
                ob = await self.client.watch_order_book(symbol, limit=10)
                self.order_book.update_order_book(ob.get("bids", []), ob.get("asks", []))
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(1)

    async def _stream_trades(self, symbol):
        while True:
            try:
                trades = await self.client.watch_trades(symbol)
                self.recent_trades.add_trades(trades)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(1)

    def _on_symbols_changed(self, symbols):
        self._selected_symbols = symbols
        self._start_streams()
        if symbols:
            asyncio.ensure_future(self._update_chart(symbols[0]))

    async def _update_chart(self, symbol):
        await self.chart.set_symbol(symbol)

    async def _refresh_positions(self):
        try:
            positions = await self.position_mgr.get_open_positions()
            pos_list = [p.dict() for p in positions]
            self.positions_table.update_positions(pos_list)
            balance = await self.client.fetch_balance()
            self.account_balance.update_balance(balance)
            risk_report = await self.risk_mgr.get_risk_report()
            self.risk_monitor.update_risk(risk_report)
        except Exception as e:
            logger.error(f"Refresh error: {e}")

    def _async_refresh(self):
        asyncio.ensure_future(self._refresh_positions())

    def _on_execute(self, base_req: TradeRequest):
        if not self._selected_symbols:
            QMessageBox.warning(self, "No symbols", "Select symbols first.")
            return
        requests = []
        for sym in self._selected_symbols:
            req = base_req.copy(update={"symbol": sym})
            requests.append(req)
        asyncio.ensure_future(self._execute_orders(requests))

    async def _execute_orders(self, requests):
        try:
            balance = await self.client.fetch_balance()
            equity = float(balance.get("total", {}).get("USDT", 0))
            positions = await self.position_mgr.get_open_positions()
            allowed, reason = await self.risk_mgr.validate_batch(requests, equity, positions)
            if not allowed:
                QMessageBox.critical(self, "Risk Blocked", reason)
                return
            results = await self.executor.execute_orders(requests)
            for res in results:
                logger.info(f"{res.symbol}: {res.message}")
                if self.nm and self.config.notifications.trade_alert.enabled:
                    await self.nm.notify(NotificationMessage(
                        title=f"Trade {res.symbol}",
                        body=f"{'BUY' if res.side == 'buy' else 'SELL'} {res.filled_quantity} @ {res.avg_price:.2f} | {res.message}",
                        level="info" if res.success else "critical",
                        category="trade",
                        metadata=res.dict()
                    ))
                await self.risk_mgr.record_trade_result(res.success, pnl=0)
            await self._refresh_positions()
        except Exception as e:
            logger.exception(f"Execution error: {e}")

    def _on_close_position(self, symbol: str):
        asyncio.ensure_future(self._close_position(symbol))

    async def _close_position(self, symbol):
        reply = QMessageBox.question(self, "Confirm", f"Close position for {symbol}?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            result = await self.position_mgr.partial_close(symbol, 100.0)
            logger.info(f"Close {symbol}: {result.message}")
            await self._refresh_positions()

    def closeEvent(self, event):
        self._save_state()
        event.accept()

    def _save_state(self):
        self._settings.setValue("geometry", self.saveGeometry())
        self._settings.setValue("windowState", self.saveState())

    def _load_state(self):
        geometry = self._settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        state = self._settings.value("windowState")
        if state:
            self.restoreState(state)