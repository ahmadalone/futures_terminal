#!/usr/bin/env python3
"""
check_missing.py – Verify that all required files exist in futures_terminal/.
Usage: python check_missing.py
"""

import os
from pathlib import Path

# The exact same mapping used by organize.py
EXPECTED_FILES = {
    "main.py":                              "main.py",
    "config.yaml":                          "config.yaml",
    ".env.example":                         ".env.example",
    "requirements.txt":                     "requirements.txt",
    "VERSION":                              "VERSION",
    "pytest.ini":                           "pytest.ini",
    "Dockerfile":                           "Dockerfile",
    ".dockerignore":                        ".dockerignore",
    "docker-compose.yml":                   "docker-compose.yml",
    "setup.py":                             "setup.py",

    ".github/workflows/ci.yml":             ".github/workflows/ci.yml",

    "scripts/entrypoint.sh":                "scripts/entrypoint.sh",

    "exchange/futures_client.py":           "exchange/futures_client.py",
    "exchange/__init__.py":                 "exchange/__init__.py",

    "execution/order_executor.py":          "execution/order_executor.py",
    "execution/position_manager.py":        "execution/position_manager.py",
    "execution/risk_manager.py":            "execution/risk_manager.py",
    "execution/signal_executor.py":         "execution/signal_executor.py",
    "execution/portfolio_allocator.py":     "execution/portfolio_allocator.py",
    "execution/__init__.py":                "execution/__init__.py",

    "models/trade_request.py":              "models/trade_request.py",
    "models/trade_result.py":               "models/trade_result.py",
    "models/order.py":                      "models/order.py",
    "models/position.py":                   "models/position.py",
    "models/account.py":                    "models/account.py",
    "models/exceptions.py":                 "models/exceptions.py",
    "models/risk_metrics.py":               "models/risk_metrics.py",
    "models/signal.py":                     "models/signal.py",
    "models/analytics_report.py":           "models/analytics_report.py",
    "models/backtest_result.py":            "models/backtest_result.py",
    "models/notification.py":               "models/notification.py",
    "models/__init__.py":                   "models/__init__.py",

    "utils/config.py":                      "utils/config.py",
    "utils/logger.py":                      "utils/logger.py",
    "utils/__init__.py":                    "utils/__init__.py",

    "database/db.py":                       "database/db.py",
    "database/__init__.py":                 "database/__init__.py",

    "gui/main_window.py":                   "gui/main_window.py",
    "gui/dark_theme.py":                    "gui/dark_theme.py",
    "gui/__init__.py":                      "gui/__init__.py",

    "gui/widgets/watchlist.py":             "gui/widgets/watchlist.py",
    "gui/widgets/trade_panel.py":           "gui/widgets/trade_panel.py",
    "gui/widgets/positions_table.py":       "gui/widgets/positions_table.py",
    "gui/widgets/order_book.py":            "gui/widgets/order_book.py",
    "gui/widgets/recent_trades.py":         "gui/widgets/recent_trades.py",
    "gui/widgets/account_balance.py":       "gui/widgets/account_balance.py",
    "gui/widgets/risk_monitor.py":          "gui/widgets/risk_monitor.py",
    "gui/widgets/log_widget.py":            "gui/widgets/log_widget.py",
    "gui/widgets/chart_widget.py":          "gui/widgets/chart_widget.py",
    "gui/widgets/performance_dashboard.py": "gui/widgets/performance_dashboard.py",
    "gui/widgets/__init__.py":              "gui/widgets/__init__.py",

    "gui/chart_engine/candlestick_item.py": "gui/chart_engine/candlestick_item.py",
    "gui/chart_engine/chart_widget.py":     "gui/chart_engine/chart_widget.py",
    "gui/chart_engine/indicators.py":       "gui/chart_engine/indicators.py",
    "gui/chart_engine/drawing_tools.py":    "gui/chart_engine/drawing_tools.py",
    "gui/chart_engine/timeframe_manager.py":"gui/chart_engine/timeframe_manager.py",
    "gui/chart_engine/dom_heatmap.py":      "gui/chart_engine/dom_heatmap.py",
    "gui/chart_engine/replay_manager.py":   "gui/chart_engine/replay_manager.py",
    "gui/chart_engine/__init__.py":         "gui/chart_engine/__init__.py",

    "strategies/base.py":                   "strategies/base.py",
    "strategies/loader.py":                 "strategies/loader.py",
    "strategies/manager.py":                "strategies/manager.py",
    "strategies/ai_strategy.py":            "strategies/ai_strategy.py",
    "strategies/__init__.py":               "strategies/__init__.py",

    "ai/feature_engine.py":                 "ai/feature_engine.py",
    "ai/model_manager.py":                  "ai/model_manager.py",
    "ai/prediction_engine.py":              "ai/prediction_engine.py",
    "ai/online_learner.py":                 "ai/online_learner.py",
    "ai/prediction_models.py":              "ai/prediction_models.py",
    "ai/__init__.py":                       "ai/__init__.py",

    "analytics/trade_journal.py":           "analytics/trade_journal.py",
    "analytics/performance.py":             "analytics/performance.py",
    "analytics/equity_curve.py":            "analytics/equity_curve.py",
    "analytics/reports.py":                 "analytics/reports.py",
    "analytics/heatmap.py":                 "analytics/heatmap.py",
    "analytics/__init__.py":                "analytics/__init__.py",

    "notifications/base.py":                "notifications/base.py",
    "notifications/telegram.py":            "notifications/telegram.py",
    "notifications/discord.py":             "notifications/discord.py",
    "notifications/email_.py":              "notifications/email_.py",
    "notifications/desktop.py":             "notifications/desktop.py",
    "notifications/manager.py":             "notifications/manager.py",
    "notifications/__init__.py":            "notifications/__init__.py",

    "backtesting/data_loader.py":           "backtesting/data_loader.py",
    "backtesting/engine.py":                "backtesting/engine.py",
    "backtesting/walkforward.py":           "backtesting/walkforward.py",
    "backtesting/portfolio_simulator.py":   "backtesting/portfolio_simulator.py",
    "backtesting/optimization.py":          "backtesting/optimization.py",
    "backtesting/monte_carlo.py":           "backtesting/monte_carlo.py",
    "backtesting/report.py":                "backtesting/report.py",
    "backtesting/__init__.py":              "backtesting/__init__.py",

    "plugins/base.py":                      "plugins/base.py",
    "plugins/manifest.py":                  "plugins/manifest.py",
    "plugins/manager.py":                   "plugins/manager.py",
    "plugins/services.py":                  "plugins/services.py",
    "plugins/__init__.py":                  "plugins/__init__.py",
    "plugins/examples/ma_crossover.py":     "plugins/examples/ma_crossover.py",
    "plugins/examples/manifest.json":       "plugins/examples/manifest.json",

    "optimization/cache.py":                "optimization/cache.py",
    "optimization/profiler.py":             "optimization/profiler.py",
    "optimization/async_helpers.py":        "optimization/async_helpers.py",
    "optimization/memory.py":               "optimization/memory.py",
    "optimization/thread_safety.py":        "optimization/thread_safety.py",
    "optimization/db_optimizer.py":         "optimization/db_optimizer.py",
    "optimization/__init__.py":             "optimization/__init__.py",

    "tests/conftest.py":                    "tests/conftest.py",
    "tests/test_models.py":                 "tests/test_models.py",
    "tests/test_config.py":                 "tests/test_config.py",
    "tests/test_database.py":               "tests/test_database.py",
    "tests/test_logger.py":                 "tests/test_logger.py",
    "tests/test_exchange_client.py":        "tests/test_exchange_client.py",
    "tests/test_order_executor.py":         "tests/test_order_executor.py",
    "tests/test_position_manager.py":       "tests/test_position_manager.py",
    "tests/test_risk_manager.py":           "tests/test_risk_manager.py",
    "tests/test_notifications.py":          "tests/test_notifications.py",
    "tests/test_strategies.py":             "tests/test_strategies.py",
    "tests/test_backtesting.py":            "tests/test_backtesting.py",
    "tests/test_integration.py":            "tests/test_integration.py",
    "tests/test_performance.py":            "tests/test_performance.py",
    "tests/test_gui.py":                    "tests/test_gui.py",
    "tests/__init__.py":                    "tests/__init__.py",

    "assets/style.qss":                     "assets/style.qss",

    "docs/plugins.md":                      "docs/plugins.md",
    "docs/README.md":                       "docs/README.md",
}

ROOT = "futures_terminal"

def check():
    missing = []
    for src, dst in EXPECTED_FILES.items():
        path = os.path.join(ROOT, dst)
        if not os.path.exists(path):
            missing.append(dst)
    if missing:
        print(f"Missing {len(missing)} files in {ROOT}/:")
        for f in missing:
            print(f"  - {f}")
    else:
        print("✅ All expected files are present!")

if __name__ == "__main__":
    check()