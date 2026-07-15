"""
Custom pyqtgraph items for candlesticks and volume bars.
"""
import numpy as np
import pyqtgraph as pg
from pyqtgraph import QtCore, QtGui
from typing import List, Tuple

class CandlestickItem(pg.GraphicsObject):
    """
    Draws OHLC candlesticks. Data: list of (time, open, high, low, close).
    """
    def __init__(self, data: List[Tuple[float, float, float, float, float]] = None):
        super().__init__()
        self.data = data or []
        self.picture = QtGui.QPicture()
        self._generate_picture()

    def set_data(self, data: List[Tuple[float, float, float, float, float]]):
        self.data = data
        self._generate_picture()
        self.update()

    def _generate_picture(self):
        if not self.data:
            self.picture = QtGui.QPicture()
            return
        painter = QtGui.QPainter()
        painter.begin(self.picture)
        w = self._calculate_body_width()
        for t, o, h, l, c in self.data:
            if c >= o:
                color = QtGui.QColor(0, 255, 0)
                body_top, body_bottom = o, c
            else:
                color = QtGui.QColor(255, 0, 0)
                body_top, body_bottom = c, o
            painter.setPen(pg.mkPen(color, width=1))
            painter.drawLine(QtCore.QPointF(t, l), QtCore.QPointF(t, h))
            if body_bottom != body_top:
                body_rect = QtCore.QRectF(t - w/2, body_bottom, w, body_top - body_bottom)
                painter.fillRect(body_rect, color)
            else:
                painter.drawLine(QtCore.QPointF(t - w/2, c), QtCore.QPointF(t + w/2, c))
        painter.end()

    def _calculate_body_width(self) -> float:
        if len(self.data) < 2:
            return 1.0
        avg_delta = (self.data[-1][0] - self.data[0][0]) / max(1, len(self.data) - 1)
        return avg_delta * 0.6

    def paint(self, painter, option, widget):
        painter.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        return QtCore.QRectF(self.picture.boundingRect())


class VolumeBarItem(pg.GraphicsObject):
    """
    Plots volume bars. Data: list of (time, volume, close, open).
    """
    def __init__(self, data: List[Tuple[float, float, float, float]] = None):
        super().__init__()
        self.data = data or []
        self.picture = QtGui.QPicture()
        self._generate_picture()

    def set_data(self, data: List[Tuple[float, float, float, float]]):
        self.data = data
        self._generate_picture()
        self.update()

    def _generate_picture(self):
        if not self.data:
            self.picture = QtGui.QPicture()
            return
        painter = QtGui.QPainter()
        painter.begin(self.picture)
        max_vol = max(v[1] for v in self.data) if self.data else 1
        w = self._calculate_body_width()
        for t, vol, close, open_ in self.data:
            color = QtGui.QColor(0, 255, 0) if close >= open_ else QtGui.QColor(255, 0, 0)
            height = (vol / max_vol) * 1.0
            if height > 0:
                rect = QtCore.QRectF(t - w/2, 0, w, height)
                painter.fillRect(rect, color)
        painter.end()

    def _calculate_body_width(self):
        if len(self.data) < 2:
            return 1.0
        avg_delta = (self.data[-1][0] - self.data[0][0]) / max(1, len(self.data) - 1)
        return avg_delta * 0.6

    def paint(self, painter, option, widget):
        painter.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        return QtCore.QRectF(self.picture.boundingRect())