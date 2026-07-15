"""
Main chart widget – candlesticks, volume, indicators, drawing tools.
"""
import asyncio
import pyqtgraph as pg
from pyqtgraph import QtCore, QtGui, QtWidgets
from typing import List, Optional, Dict
from exchange.futures_client import BinanceFuturesClient
from .candlestick_item import CandlestickItem, VolumeBarItem
from .indicators import IndicatorManager
from .drawing_tools import DrawingToolManager
from .timeframe_manager import TimeframeManager
from .dom_heatmap import DOMHeatmapWidget
from .replay_manager import ReplayManager
from utils.logger import setup_logger

logger = setup_logger(__name__)

class ChartWidget(QtWidgets.QWidget):
    """
    Professional chart with multiple timeframes, indicators, and replay.
    """
    def __init__(self, client: BinanceFuturesClient, parent=None):
        super().__init__(parent)
        self.client = client
        self.symbol: Optional[str] = None
        self.timeframe = "5m"
        self.timeframe_manager = TimeframeManager(client)
        self.indicator_manager = IndicatorManager()
        self.drawing_tool = DrawingToolManager()
        self._data_cache: Dict[str, List[List[float]]] = {}

        self._init_ui()
        self._connect_signals()
        self.replay_manager = ReplayManager(self)

    def _init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        toolbar = QtWidgets.QHBoxLayout()
        self.tf_combo = QtWidgets.QComboBox()
        self.tf_combo.addItems(["1m", "5m", "15m", "1h", "4h", "1d"])
        self.tf_combo.setCurrentText("5m")
        toolbar.addWidget(QtWidgets.QLabel("Timeframe:"))
        toolbar.addWidget(self.tf_combo)

        self.indicator_btn = QtWidgets.QPushButton("Indicators")
        self.indicator_btn.clicked.connect(self._show_indicator_menu)
        toolbar.addWidget(self.indicator_btn)

        self.replay_btn = QtWidgets.QPushButton("Replay")
        self.replay_btn.setCheckable(True)
        toolbar.addWidget(self.replay_btn)

        toolbar.addStretch()
        main_layout.addLayout(toolbar)

        # Graphics
        self.graphics_layout = pg.GraphicsLayoutWidget()
        main_layout.addWidget(self.graphics_layout)

        self.price_plot = self.graphics_layout.addPlot(row=0, col=0)
        self.volume_plot = self.graphics_layout.addPlot(row=1, col=0)
        self.volume_plot.setXLink(self.price_plot)

        self.price_plot.showGrid(x=True, y=True, alpha=0.3)
        self.price_plot.setLabel('left', 'Price')
        self.volume_plot.setLabel('left', 'Volume')

        self.candle_item = CandlestickItem()
        self.volume_item = VolumeBarItem()
        self.price_plot.addItem(self.candle_item)
        self.volume_plot.addItem(self.volume_item)

        self.indicator_manager.set_plots(self.price_plot, self.volume_plot)
        self.drawing_tool.attach_to_plot(self.price_plot)

        self._setup_crosshair()

    def _setup_crosshair(self):
        self.v_line = pg.InfiniteLine(angle=90, movable=False)
        self.h_line = pg.InfiniteLine(angle=0, movable=False)
        self.price_plot.addItem(self.v_line, ignoreBounds=True)
        self.price_plot.addItem(self.h_line, ignoreBounds=True)
        self.v_line.hide()
        self.h_line.hide()
        self.proxy = pg.SignalProxy(self.price_plot.scene().sigMouseMoved, rateLimit=60, slot=self._mouse_moved)

    def _mouse_moved(self, evt):
        pos = evt[0]
        if self.price_plot.sceneBoundingRect().contains(pos):
            mouse_point = self.price_plot.vb.mapSceneToView(pos)
            self.v_line.setPos(mouse_point.x())
            self.h_line.setPos(mouse_point.y())
            self.v_line.show()
            self.h_line.show()
        else:
            self.v_line.hide()
            self.h_line.hide()

    def _connect_signals(self):
        self.tf_combo.currentTextChanged.connect(lambda tf: asyncio.ensure_future(self._on_timeframe_changed(tf)))
        self.replay_btn.toggled.connect(self._on_replay_toggled)

    async def set_symbol(self, symbol: str):
        self.symbol = symbol
        self.price_plot.setTitle(symbol)
        await self._load_and_draw()

    async def _on_timeframe_changed(self, tf: str):
        self.timeframe = tf
        if self.symbol:
            await self._load_and_draw()

    async def _load_and_draw(self):
        if not self.symbol:
            return
        try:
            ohlcv = await self.timeframe_manager.fetch_ohlcv(self.symbol, self.timeframe)
            if ohlcv:
                self._data_cache[self.timeframe] = ohlcv
                self._update_chart(ohlcv)
                self.indicator_manager.update(ohlcv, self.symbol, self.timeframe)
        except Exception as e:
            logger.error(f"Chart load error: {e}")

    def _update_chart(self, ohlcv):
        candle_data = [(c[0], c[1], c[2], c[3], c[4]) for c in ohlcv]
        self.candle_item.set_data(candle_data)

        vol_data = [(c[0], c[5], c[4], c[1]) for c in ohlcv]
        self.volume_item.set_data(vol_data)
        if vol_data:
            max_vol = max(v[1] for v in vol_data)
            self.volume_plot.setYRange(0, max_vol * 1.1)
        self.price_plot.autoRange()

    def _show_indicator_menu(self):
        menu = QtWidgets.QMenu(self)
        for ind in IndicatorManager.AVAILABLE_INDICATORS:
            action = menu.addAction(ind)
            action.setCheckable(True)
            action.setChecked(self.indicator_manager.is_active(ind))
            action.triggered.connect(lambda checked, name=ind: self._toggle_indicator(name))
        menu.exec(self.indicator_btn.mapToGlobal(QtCore.QPoint(0, self.indicator_btn.height())))

    def _toggle_indicator(self, name: str):
        self.indicator_manager.toggle(name)
        if self.symbol and self.timeframe in self._data_cache:
            self.indicator_manager.update(self._data_cache[self.timeframe], self.symbol, self.timeframe)

    def _on_replay_toggled(self, checked: bool):
        if checked:
            self.replay_manager.start()
        else:
            self.replay_manager.stop()

    def update_from_replay(self, data_slice):
        self._update_chart(data_slice)
