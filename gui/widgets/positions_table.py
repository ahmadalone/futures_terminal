from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QHBoxLayout,
    QHeaderView, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from typing import List, Dict
import asyncio

class PositionsTable(QWidget):
    close_position_signal = Signal(str)      # symbol
    partial_close_signal = Signal(str, float)  # symbol, percentage

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Symbol", "Side", "Qty", "Entry", "Mark", "PnL", "Liq", "Action"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

    def update_positions(self, positions: List[Dict]):
        self.table.setRowCount(len(positions))
        for i, pos in enumerate(positions):
            self.table.setItem(i, 0, QTableWidgetItem(pos.get("symbol", "")))
            self.table.setItem(i, 1, QTableWidgetItem(pos.get("side", "")))
            self.table.setItem(i, 2, QTableWidgetItem(f"{pos.get('quantity', 0):.4f}"))
            self.table.setItem(i, 3, QTableWidgetItem(f"{pos.get('entry_price', 0):.2f}"))
            self.table.setItem(i, 4, QTableWidgetItem(f"{pos.get('mark_price', 0):.2f}"))
            pnl = pos.get("unrealized_pnl", 0)
            pnl_item = QTableWidgetItem(f"{pnl:.2f}")
            pnl_item.setForeground(Qt.green if pnl >= 0 else Qt.red)
            self.table.setItem(i, 5, pnl_item)
            self.table.setItem(i, 6, QTableWidgetItem(f"{pos.get('liquidation_price', 0):.2f}"))
            # Action buttons
            close_btn = QPushButton("Close 100%")
            close_btn.clicked.connect(lambda checked, sym=pos["symbol"]: self.close_position_signal.emit(sym))
            self.table.setCellWidget(i, 7, close_btn)