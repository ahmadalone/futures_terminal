"""
Depth of Market heatmap widget using order book data.
"""
import asyncio
import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QWidget, QVBoxLayout
from exchange.futures_client import BinanceFuturesClient

class DOMHeatmapWidget(QWidget):
    def __init__(self, client: BinanceFuturesClient):
        super().__init__()
        self.client = client
        self.plot = pg.PlotWidget()
        layout = QVBoxLayout(self)
        layout.addWidget(self.plot)
        self.symbol = None
        self._task = None

    async def start_stream(self, symbol: str):
        self.symbol = symbol
        if self._task:
            self._task.cancel()
        self._task = asyncio.ensure_future(self._stream())

    async def _stream(self):
        while True:
            try:
                ob = await self.client.watch_order_book(self.symbol, limit=100)
                bids = np.array(ob.get("bids", []), dtype=float)
                asks = np.array(ob.get("asks", []), dtype=float)
                self.plot.clear()
                if len(bids) > 0:
                    self.plot.plot(bids[:,0], np.cumsum(bids[:,1]), pen='g', stepMode=True)
                if len(asks) > 0:
                    self.plot.plot(asks[:,0], np.cumsum(asks[:,1]), pen='r', stepMode=True)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(1)