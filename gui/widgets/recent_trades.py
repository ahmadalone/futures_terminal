from PySide6.QtWidgets import QWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QHeaderView
from PySide6.QtCore import Qt
from typing import List, Dict

class RecentTradesWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Price", "Qty", "Time"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

    def add_trades(self, trades: List[Dict]):
        for trade in reversed(trades):  # newest on top
            self._add_trade(trade)

    def _add_trade(self, trade: Dict):
        row = self.table.rowCount()
        self.table.insertRow(0)
        price = trade.get("price", 0)
        qty = trade.get("amount", 0)
        color = Qt.green if trade.get("side") == "buy" else Qt.red
        self.table.setItem(0, 0, QTableWidgetItem(f"{price:.2f}"))
        item_qty = QTableWidgetItem(f"{qty:.4f}")
        item_qty.setForeground(color)
        self.table.setItem(0, 1, item_qty)
        self.table.setItem(0, 2, QTableWidgetItem(trade.get("datetime", "")))