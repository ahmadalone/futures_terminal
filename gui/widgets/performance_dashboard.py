from PySide6.QtWidgets import QWidget, QGridLayout, QLabel
from PySide6.QtCore import QTimer
import asyncio
from analytics.performance import PerformanceMetrics
from analytics.equity_curve import EquityCurve
from analytics.trade_journal import TradeJournal
from utils.logger import setup_logger

logger = setup_logger(__name__)

class PerformanceDashboard(QWidget):
    def __init__(self, db_path: str = "trading_terminal.db"):
        super().__init__()
        self.db_path = db_path
        self.equity = EquityCurve(db_path)
        self.journal = TradeJournal(db_path)
        self.metrics = PerformanceMetrics(self.equity, self.journal)

        layout = QGridLayout(self)
        self.labels = {}
        names = [
            ("Sharpe", "sharpe_ratio"),
            ("Sortino", "sortino_ratio"),
            ("Calmar", "calmar_ratio"),
            ("Max DD %", "max_drawdown_pct"),
            ("Win Rate", "win_rate"),
            ("Profit Factor", "profit_factor"),
            ("Expectancy", "expectancy"),
            ("Total Trades", "total_trades"),
            ("Total PnL", "total_profit"),
        ]
        for i, (label, key) in enumerate(names):
            lbl = QLabel(label + ":")
            val = QLabel("--")
            layout.addWidget(lbl, i//3, (i%3)*2)
            layout.addWidget(val, i//3, (i%3)*2+1)
            self.labels[key] = val

        self.timer = QTimer()
        self.timer.timeout.connect(lambda: asyncio.ensure_future(self.update_metrics()))
        self.timer.start(5000)
        asyncio.ensure_future(self.update_metrics())

    async def update_metrics(self):
        try:
            report = await self.metrics.compute()
            for key, val in report.dict().items():
                if key in self.labels:
                    self.labels[key].setText(str(val))
        except Exception as e:
            logger.error(f"Dashboard update error: {e}")