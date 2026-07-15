#!/usr/bin/env python3
"""
Futures Trading Terminal – Main Entry Point (robust)
"""
import sys
import asyncio
from pathlib import Path
from datetime import datetime, timedelta

import qasync
from PySide6.QtWidgets import QApplication

# ----------------------------------------------------------------------
# Core utilities (always present)
# ----------------------------------------------------------------------
from utils.config import load_config, AppConfig
from utils.logger import setup_logger
from database.db import init_db

# ----------------------------------------------------------------------
# Exchange & execution (required)
# ----------------------------------------------------------------------
from exchange.futures_client import BinanceFuturesClient
from execution.order_executor import OrderExecutor
from execution.position_manager import PositionManager
from execution.risk_manager import RiskManager

# ----------------------------------------------------------------------
# Optional imports – wrapped later
# ----------------------------------------------------------------------
try:
    from execution.signal_executor import SignalExecutor
    from execution.portfolio_allocator import PortfolioAllocator
    SIGNAL_SYSTEM = True
except ImportError:
    SIGNAL_SYSTEM = False

try:
    from strategies.loader import StrategyLoader
    from strategies.manager import StrategyManager
    STRATEGY_SYSTEM = True
except ImportError:
    STRATEGY_SYSTEM = False

try:
    from notifications.manager import NotificationManager
    from notifications.telegram import TelegramNotifier
    from notifications.discord import DiscordNotifier
    from notifications.email_ import EmailNotifier
    from notifications.desktop import DesktopNotifier
    NOTIFICATIONS = True
except ImportError:
    NOTIFICATIONS = False

try:
    from plugins.manager import PluginManager
    from plugins.services import ServiceRegistry
    PLUGINS = True
except ImportError:
    PLUGINS = False

try:
    from ai.prediction_engine import PredictionEngine
    from ai.online_learner import OnlineLearner
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False

try:
    from optimization.async_helpers import TaskPool
    from optimization.profiler import Profiler
    OPTIMIZATION = True
except ImportError:
    OPTIMIZATION = False

# ----------------------------------------------------------------------
# Version
# ----------------------------------------------------------------------
def get_version():
    try:
        return Path("VERSION").read_text().strip()
    except Exception:
        return "dev"


async def main():
    # ------------------------------------------------------------------
    # 1. Configuration & logging
    # ------------------------------------------------------------------
    config: AppConfig = load_config()
    log_cfg = config.logging

    # Command-line flags
    verbose = "-v" in sys.argv or "--debug" in sys.argv
    if verbose:
        log_cfg.level = "DEBUG"
        print("Verbose mode enabled")

    logger = setup_logger(
        level=log_cfg.level,
        log_file=log_cfg.file,
        max_bytes=log_cfg.max_bytes,
        backup_count=log_cfg.backup_count,
        fmt=log_cfg.format,
        datefmt=log_cfg.datefmt,
    )
    logger.info(f"Starting Futures Terminal v{get_version()}")

    # ------------------------------------------------------------------
    # 2. Database
    # ------------------------------------------------------------------
    await init_db(config.database.path)
    logger.info("Database ready")

    # ------------------------------------------------------------------
    # 3. Exchange client
    # ------------------------------------------------------------------
    ex_cfg = config.exchange
    api_key = ex_cfg.get("api_key", "")
    secret = ex_cfg.get("secret", "")
    testnet = ex_cfg.get("testnet", False)

    if not api_key or not secret:
        logger.error("API key or secret missing in configuration. Set in .env or config.yaml")
        sys.exit(1)

    client = BinanceFuturesClient(api_key, secret, testnet)

    # Load markets with controlled concurrency (if optimization available)
    if OPTIMIZATION:
        pool = TaskPool(max_concurrency=2)
        await pool.submit(client.load_markets())
        await pool.join()
    else:
        await client.load_markets()
    logger.info("Exchange markets loaded")

    # ------------------------------------------------------------------
    # 4. Core managers
    # ------------------------------------------------------------------
    executor = OrderExecutor(client, config.database.path)
    position_mgr = PositionManager(client, executor, config.database.path)
    risk_mgr = RiskManager(config, client, position_mgr, config.database.path)
    await risk_mgr.initialize()
    logger.info("Risk Manager initialized")

    # ------------------------------------------------------------------
    # 5. Signal / Strategy system (optional)
    # ------------------------------------------------------------------
    strategy_mgr = None
    signal_exec = None
    if STRATEGY_SYSTEM and SIGNAL_SYSTEM:
        try:
            allocator = PortfolioAllocator(config.strategies.allocation)
            signal_exec = SignalExecutor(executor, risk_mgr, allocator)

            strategy_loader = StrategyLoader("strategies")
            strategy_mgr = StrategyManager(client, strategy_loader, config.strategies)

            async def handle_signals(signals):
                balance = await client.fetch_balance()
                equity = float(balance.get("total", {}).get("USDT", 0))
                await signal_exec.execute_signals(signals, equity)

            strategy_mgr.set_signal_callback(handle_signals)
            await strategy_mgr.start()
            logger.info("Strategy system started")
        except Exception as e:
            logger.error(f"Strategy system initialization failed: {e}")
    else:
        logger.info("Strategy system not available (missing modules)")

    # ------------------------------------------------------------------
    # 6. Notifications (optional)
    # ------------------------------------------------------------------
    nm = None
    if NOTIFICATIONS:
        try:
            nm = NotificationManager()
            notif_cfg = config.notifications
            if notif_cfg.telegram.enabled and notif_cfg.telegram.bot_token:
                nm.add_notifier(TelegramNotifier(notif_cfg.telegram.bot_token, notif_cfg.telegram.chat_id))
            if notif_cfg.discord.enabled and notif_cfg.discord.webhook_url:
                nm.add_notifier(DiscordNotifier(notif_cfg.discord.webhook_url))
            if notif_cfg.email.enabled and notif_cfg.email.username:
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
                    from models.notification import NotificationMessage
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
            logger.info("Notification system started")
        except Exception as e:
            logger.error(f"Notification setup failed: {e}")

    # ------------------------------------------------------------------
    # 7. AI Engine (optional)
    # ------------------------------------------------------------------
    if AI_AVAILABLE and config.ai.models:
        try:
            ai_engine = PredictionEngine(client, config.ai.dict())
            if config.ai.online_learning.get("symbols"):
                learner = OnlineLearner(ai_engine, interval_hours=config.ai.online_learning.get("interval_hours", 1))
                await learner.start(config.ai.online_learning["symbols"], "5m")
                logger.info("AI online learner started")
        except Exception as e:
            logger.error(f"AI engine failed: {e}")

    # ------------------------------------------------------------------
    # 8. Plugin system (optional)
    # ------------------------------------------------------------------
    if PLUGINS and config.plugins.auto_load:
        try:
            services = ServiceRegistry(client, nm, risk_mgr, position_mgr, executor)
            plugin_mgr = PluginManager(services, config.plugins.directories)
            plugins = plugin_mgr.load_all()
            await plugin_mgr.start_all()
            for p in plugins:
                class Adapter:
                    def __init__(self, plugin):
                        self.name = plugin.manifest.name
                        self.symbols = plugin.manifest.symbols
                        self.enabled = True
                        self.on_tick = plugin.on_tick
                    async def on_start(self): pass
                    async def on_stop(self): pass
                if strategy_mgr:
                    strategy_mgr._strategies[p.manifest.name] = Adapter(p)
            logger.info(f"Loaded {len(plugins)} plugin(s)")
        except Exception as e:
            logger.error(f"Plugin system failed: {e}")

    # ------------------------------------------------------------------
    # 9. GUI or Headless mode
    # ------------------------------------------------------------------
    if "--no-gui" in sys.argv:
        logger.info("Headless mode – terminal running without GUI")
        try:
            while True:
                await asyncio.sleep(3600)
        except KeyboardInterrupt:
            logger.info("Shutdown signal received")
        return

    # GUI
    try:
        from gui.main_window import MainWindow
        from gui.dark_theme import load_dark_theme
    except ImportError as e:
        logger.error(f"Cannot start GUI: {e}")
        sys.exit(1)

    app = QApplication(sys.argv)
    load_dark_theme(app)

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = MainWindow(client, executor, position_mgr, risk_mgr, config, nm)
    window.show()

    if OPTIMIZATION:
        async with Profiler("Event Loop"):
            with loop:
                loop.run_forever()
    else:
        with loop:
            loop.run_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
