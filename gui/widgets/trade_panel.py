from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QComboBox, QDoubleSpinBox,
    QSpinBox, QPushButton, QGroupBox, QCheckBox, QRadioButton, QButtonGroup
)
from PySide6.QtCore import Signal
from models.trade_request import TradeRequest

class TradePanel(QWidget):
    execute_signal = Signal(object)  # TradeRequest or list?

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        group = QGroupBox("Order Entry")
        form = QFormLayout()

        self.side_combo = QComboBox()
        self.side_combo.addItems(["Buy", "Sell"])
        form.addRow("Side:", self.side_combo)

        self.order_type = QComboBox()
        self.order_type.addItems(["Market", "Limit", "Stop Market", "Stop Limit", "Trailing Stop"])
        form.addRow("Type:", self.order_type)

        self.sizing_mode = QComboBox()
        self.sizing_mode.addItems(["Fixed USDT", "% of Equity", "Fixed Qty", "Risk Based", "ATR Based"])
        form.addRow("Sizing:", self.sizing_mode)

        self.amount = QDoubleSpinBox()
        self.amount.setRange(0, 1e9)
        self.amount.setValue(100)
        self.amount.setPrefix("$")
        form.addRow("Amount:", self.amount)

        self.leverage = QSpinBox()
        self.leverage.setRange(1, 125)
        self.leverage.setValue(10)
        form.addRow("Leverage:", self.leverage)

        self.stop_loss = QDoubleSpinBox()
        self.stop_loss.setRange(0, 100)
        self.stop_loss.setValue(2.0)
        self.stop_loss.setSuffix("%")
        form.addRow("Stop Loss:", self.stop_loss)

        self.take_profit = QDoubleSpinBox()
        self.take_profit.setRange(0, 1000)
        self.take_profit.setValue(4.0)
        self.take_profit.setSuffix("%")
        form.addRow("Take Profit:", self.take_profit)

        self.reduce_only = QCheckBox("Reduce Only")
        form.addRow(self.reduce_only)

        self.margin_mode = QComboBox()
        self.margin_mode.addItems(["Isolated", "Cross"])
        form.addRow("Margin:", self.margin_mode)

        group.setLayout(form)
        layout.addWidget(group)

        self.execute_btn = QPushButton("EXECUTE")
        self.execute_btn.clicked.connect(self._on_execute)
        layout.addWidget(self.execute_btn)

    def get_trade_request(self) -> TradeRequest:
        side = "buy" if self.side_combo.currentText() == "Buy" else "sell"
        order_type = self.order_type.currentText().lower().replace(" ", "_")
        sizing_text = self.sizing_mode.currentText().lower().replace(" ", "_").replace("%", "percent")
        # mapping
        sizing_map = {
            "fixed_usdt": "fixed_usdt",
            "%_of_equity": "percent_equity",
            "fixed_qty": "fixed_qty",
            "risk_based": "risk_based",
            "atr_based": "atr_based",
        }
        sizing_mode = sizing_map.get(sizing_text, "fixed_usdt")

        usd_val = self.amount.value()
        qty = usd_val if sizing_mode == "fixed_qty" else None

        return TradeRequest(
            symbol="",  # will be set by caller per selected symbol
            side=side,
            order_type=order_type,
            usd_amount=usd_val if sizing_mode != "fixed_qty" else None,
            quantity=qty,
            leverage=self.leverage.value(),
            reduce_only=self.reduce_only.isChecked(),
            stop_loss_pct=self.stop_loss.value(),
            take_profit_pct=self.take_profit.value(),
            sizing_mode=sizing_mode,
            margin_mode=self.margin_mode.currentText().lower(),
        )

    def _on_execute(self):
        self.execute_signal.emit(self.get_trade_request())