from PySide6.QtWidgets import QWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QHeaderView
from PySide6.QtCore import Qt
from typing import List, Dict
import asyncio

class OrderBookWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Price", "Amount", "Total"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)
        self._bids = []
        self._asks = []

    def update_order_book(self, bids: List[List[float]], asks: List[List[float]]):
        self._bids = bids[:10]  # top 10
        self._asks = asks[:10]
        self._redraw()

    def _redraw(self):
        self.table.setRowCount(len(self._asks) + len(self._bids))
        row = 0
        # Asks (red) – reversed so best ask at top
        for price, qty in reversed(self._asks):
            self._set_row(row, price, qty, Qt.red)
            row += 1
        # Bids (green)
        for price, qty in self._bids:
            self._set_row(row, price, qty, Qt.green)
            row += 1

    def _set_row(self, row, price, qty, color):
        self.table.setItem(row, 0, QTableWidgetItem(f"{price:.2f}"))
        item1 = QTableWidgetItem(f"{qty:.4f}")
        item1.setForeground(color)
        self.table.setItem(row, 1, item1)
        total = price * qty
        self.table.setItem(row, 2, QTableWidgetItem(f"{total:.2f}"))