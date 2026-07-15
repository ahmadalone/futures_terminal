from PySide6.QtWidgets import QWidget, QFormLayout, QLabel
from typing import Dict

class AccountBalanceWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QFormLayout(self)
        self.equity_label = QLabel("-")
        self.margin_label = QLabel("-")
        self.free_label = QLabel("-")
        self.leverage_label = QLabel("-")
        layout.addRow("Equity:", self.equity_label)
        layout.addRow("Used Margin:", self.margin_label)
        layout.addRow("Free Margin:", self.free_label)
        layout.addRow("Leverage:", self.leverage_label)

    def update_balance(self, balance: Dict):
        usdt = balance.get("USDT", {})
        self.equity_label.setText(f"${usdt.get('total', 0):.2f}")
        self.margin_label.setText(f"${usdt.get('used', 0):.2f}")
        self.free_label.setText(f"${usdt.get('free', 0):.2f}")
        # leverage = total / (total - used) approx
        total = usdt.get('total', 0)
        used = usdt.get('used', 0)
        if total and used:
            lev = total / (total - used) if (total - used) != 0 else 0
            self.leverage_label.setText(f"{lev:.2f}x")