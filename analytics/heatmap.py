"""
Daily PnL heatmap widget using a QTableWidget with colored cells.
"""
from PySide6.QtWidgets import QWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QHeaderView, QLabel
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor
from datetime import date, timedelta
import pandas as pd
from typing import Optional
from analytics.equity_curve import EquityCurve
import asyncio

class PnLHeatmapWidget(QWidget):
    def __init__(self, equity_curve: EquityCurve, parent=None):
        super().__init__(parent)
        self.equity_curve = equity_curve
        self.setLayout(QVBoxLayout())
        self.label = QLabel("Daily PnL Heatmap")
        self.layout().addWidget(self.label)
        self.table = QTableWidget()
        self.table.setColumnCount(7)  # Mon-Sun
        self.table.setHorizontalHeaderLabels(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.layout().addWidget(self.table)
        self._year = date.today().year
        self._data: Optional[pd.Series] = None

    async def refresh(self, year: int = None):
        if year is None:
            year = date.today().year
        self._year = year
        daily_pnl = await self.equity_curve.get_daily_pnl()
        if daily_pnl.empty:
            self.table.clearContents()
            return
        # Filter year
        daily_pnl = daily_pnl[daily_pnl.index.year == year]
        self._data = daily_pnl

        # Build weeks
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        # Calculate number of rows
        days = (end - start).days + 1
        weeks = (days + start.weekday()) // 7 + 1
        self.table.setRowCount(weeks)

        # Reset
        self.table.clearContents()

        for idx, val in daily_pnl.items():
            d = idx.date() if isinstance(idx, pd.Timestamp) else idx
            day_of_year = d.timetuple().tm_yday - 1
            week = day_of_year // 7
            weekday = d.weekday()
            if week < self.table.rowCount():
                item = QTableWidgetItem(f"{val:.2f}")
                # Color: green if positive, red if negative
                if val > 0:
                    item.setBackground(QColor(0, 200, 0, 150))
                elif val < 0:
                    item.setBackground(QColor(200, 0, 0, 150))
                self.table.setItem(week, weekday, item)