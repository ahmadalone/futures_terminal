from PySide6.QtWidgets import QWidget, QFormLayout, QLabel, QProgressBar
from PySide6.QtCore import Qt
from typing import Dict

class RiskMonitorWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QFormLayout(self)
        self.daily_pnl_label = QLabel("-")
        self.drawdown_label = QLabel("-")
        self.circuit_label = QLabel("OK")
        self.pause_label = QLabel("Active")
        self.drawdown_bar = QProgressBar()
        self.drawdown_bar.setMaximum(100)
        layout.addRow("Daily PnL:", self.daily_pnl_label)
        layout.addRow("Drawdown:", self.drawdown_label)
        layout.addRow("", self.drawdown_bar)
        layout.addRow("Circuit Breaker:", self.circuit_label)
        layout.addRow("Trading:", self.pause_label)

    def update_risk(self, risk_data: Dict):
        self.daily_pnl_label.setText(f"${risk_data.get('daily_pnl', 0):.2f}")
        dd = risk_data.get('drawdown_pct', 0)
        self.drawdown_label.setText(f"{dd:.2f}%")
        self.drawdown_bar.setValue(int(dd))
        if risk_data.get('circuit_breaker_triggered'):
            self.circuit_label.setText("TRIGGERED")
            self.circuit_label.setStyleSheet("color: red;")
        else:
            self.circuit_label.setText("OK")
            self.circuit_label.setStyleSheet("")
        if risk_data.get('trading_paused'):
            self.pause_label.setText("PAUSED")
            self.pause_label.setStyleSheet("color: red;")
        else:
            self.pause_label.setText("Active")
            self.pause_label.setStyleSheet("color: green;")