#!/usr/bin/env python3
import sys
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
import qasync
from PySide6.QtWidgets import QApplication

from exchange.futures_client import BinanceFuturesClient
from execution.order_executor import OrderExecutor
from execution.position_manager import PositionManager
from execution.risk_manager import RiskManager
from execution.signal_executor import SignalExecutor
from execution.portfolio_allocator import PortfolioAllocator
from strategies.loader import StrategyLoader
from strategies.manager import StrategyManager
from gui.main_window import MainWindow
from gui.dark_theme import load_dark_theme
from utils.config import load_config, AppConfig
from utils.logger import setup_logger
from database.db import init_db
from notifications.manager import NotificationManager
from notifications.telegram import TelegramNotifier
from notifications.discord import DiscordNotifier
from notifications.email_ import EmailNotifier
from notifications.desktop import DesktopNotifier
from models.notification import NotificationMessage
from optimization.async_helpers import TaskPool
from optimization.profiler import Profiler

def get_version():
    try:
        return Path("VERSION").read_text().strip()
    except Exception:
        return "dev"

async def main():
    config: AppConfig = load_config()
    log_cfg = config.logging
    logger = setup_logger(level=log_cfg.level, log_file=log_cfg.file)
    app_version = get_version()
    logger.info(f"Starting Futures Terminal v{app_version}")

    # Database
    await init_db(config.database.path)
    logger.info("Database ready")

    # Exchange client
    ex_cfg = config.exchange
    client = BinanceFuturesClient(
        api_key=ex_cfg.get("api_key", ""),
        secret=ex_cfg.get("secret", ""),
        testnet=ex_cfg.get("testnet", False),
    )
    # Load markets with controlled concurrency
    pool = TaskPool(max_concurrency=2)
    await pool.submit(client.load_markets())
    await pool.join()
    logger.info("Exchange markets loaded")

    # Managers
    executor = OrderExecutor(client, config.database.path)
    position_mgr = PositionManager(client, executor, config.database.path)
    risk_mgr = RiskManager(config, client, position_mgr, config.database.path)
    await risk_mgr.initialize()

    # Signal executor & portfolio allocator
    allocator = PortfolioAllocator(config.strategies.allocation)
    signal_exec = SignalExecutor(executor, risk_mgr, allocator)

    # Strategy system
    strategy_loader = StrategyLoader("strategies")
    strategy_mgr = StrategyManager(client, strategy_loader, config.strategies)
    async def handle_signals(signals):
        balance = await client.fetch_balance()
        equity = float(balance.get("total", {}).get("USDT", 0))
        await signal_exec.execute_signals(signals, equity)
    strategy_mgr.set_signal_callback(handle_signals)
    await strategy_mgr.start()

    # Notifications
    nm = NotificationManager()
    notif_cfg = config.notifications
    if notif_cfg.telegram.enabled:
        nm.add_notifier(TelegramNotifier(notif_cfg.telegram.bot_token, notif_cfg.telegram.chat_id))
    if notif_cfg.discord.enabled:
        nm.add_notifier(DiscordNotifier(notif_cfg.discord.webhook_url))
    if notif_cfg.email.enabled:
        nm.add_notifier(EmailNotifier(
            notif_cfg.email.smtp_host, notif_cfg.email.smtp_port,
            notif_cfg.email.username, notif_cfg.email.password,
            notif_cfg.email.recipient
        ))
    if notif_cfg.desktop.enabled:
        nm.add_notifier(DesktopNotifier())
    risk_mgr.set_notification_manager(nm)

    # Daily report task
    if notif_cfg.daily_report.enabled:
        async def daily_report_loop():
            from analytics.performance import PerformanceMetrics
            from analytics.equity_curve import EquityCurve
            from analytics.trade_journal import TradeJournal
            equity = EquityCurve(config.database.path)
            journal = TradeJournal(config.database.path)
            perf = PerformanceMetrics(equity, journal)
            while True:
                now = datetime.utcnow()
                target = datetime.strptime(notif_cfg.daily_report.time, "%H:%M").time()
                next_run = datetime.combine(now.date(), target)
                if next_run < now:
                    next_run += timedelta(days=1)
                await asyncio.sleep((next_run - now).total_seconds())
                report = await perf.compute()
                balance = await client.fetch_balance()
                equity_val = balance.get("total", {}).get("USDT", 0)
                body = (f"Equity: ${equity_val:.2f}\n"
                        f"Trades: {report.total_trades}\n"
                        f"Win Rate: {report.win_rate:.2%}\n"
                        f"PnL: ${report.total_profit:.2f}\n"
                        f"Max DD: {report.max_drawdown_pct:.2f}%\n"
                        f"Sharpe: {report.sharpe_ratio}")
                await nm.notify(NotificationMessage(
                    title="Daily Trading Report",
                    body=body,
                    level="info",
                    category="daily_report"
                ))
        asyncio.create_task(daily_report_loop())

    # Plugin system
    if config.plugins.auto_load:
        from plugins.manager import PluginManager
        from plugins.services import ServiceRegistry
        services = ServiceRegistry(client, nm, risk_mgr, position_mgr, executor)
        plugin_mgr = PluginManager(services, config.plugins.directories)
        plugins = plugin_mgr.load_all()
        await plugin_mgr.start_all()
        for p in plugins:
            # Wrap as a strategy adapter
            class Adapter:
                def __init__(self, plugin):
                    self.name = plugin.manifest.name
                    self.symbols = plugin.manifest.symbols
                    self.enabled = True
                    self.on_tick = plugin.on_tick
                async def on_start(self): pass
                async def on_stop(self): pass
            strategy_mgr._strategies[p.manifest.name] = Adapter(p)

    # GUI
    app = QApplication(sys.argv)
    load_dark_theme(app)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = MainWindow(client, executor, position_mgr, risk_mgr, config, nm)
    window.show()

    async with Profiler("Event Loop"):
        with loop:
            loop.run_forever()

if __name__ == "__main__":
    asyncio.run(main())