# Futures Terminal

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![CI](https://github.com/your-org/futures-terminal/actions/workflows/ci.yml/badge.svg)

An institutional‑grade multi‑exchange futures trading terminal built in Python with a professional PySide6 GUI, async architecture, AI‑ready signal engine, risk management, and full backtesting capabilities.

## Features
- **Multi‑exchange**: Binance, Bybit, BingX (Binance Futures full, others via ccxt)
- **Simultaneous execution** of orders across multiple symbols
- **Professional dark‑theme GUI** with dockable panels, real‑time charts, and order book
- **Risk management**: daily loss limits, circuit breakers, exposure control, Kelly sizing
- **AI Engine**: LSTM, XGBoost, LightGBM prediction models with online learning
- **Backtesting** & **walk‑forward** optimization
- **Plugin SDK**: third‑party strategy plugins
- **Notifications**: Telegram, Discord, Email, Desktop
- **Docker support** with GitHub Actions CI/CD

## Installation
### From PyPI
```bash
pip install futures-terminal
futures-terminal