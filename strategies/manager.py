"""
Strategy manager – instantiates active strategies, collects signals,
and schedules execution.
"""
import asyncio
from typing import List, Dict, Optional
from strategies.base import BaseStrategy
from strategies.loader import StrategyLoader
from models.signal import Signal
from exchange.futures_client import BinanceFuturesClient
from utils.logger import setup_logger

logger = setup_logger(__name__)

class StrategyManager:
    """
    Holds running strategy instances and orchestrates signal generation.
    Active strategies are specified in config.
    """
    def __init__(self, client: BinanceFuturesClient, loader: StrategyLoader, config: dict):
        self.client = client
        self.loader = loader
        self.config = config
        self._strategies: Dict[str, BaseStrategy] = {}
        self._tasks: List[asyncio.Task] = []
        self._running = False

    async def start(self):
        """Instantiate and start all strategies listed in config."""
        active_names = self.config.get("active", [])
        strategy_params = self.config.get("params", {})
        for name in active_names:
            cls = self.loader.get_strategy_class(name)
            if cls is None:
                logger.warning(f"Strategy {name} not found in registry")
                continue
            symbols = strategy_params.get(name, {}).get("symbols", [])
            extra_cfg = strategy_params.get(name, {}).get("config", {})
            instance = cls(name=name, symbols=symbols, config=extra_cfg)
            self._strategies[name] = instance
            logger.info(f"Strategy {name} instantiated")
        # Start scheduling loop
        self._running = True
        self._tasks.append(asyncio.create_task(self._run_loop()))

    async def stop(self):
        self._running = False
        for t in self._tasks:
            t.cancel()
        self._tasks.clear()
        self._strategies.clear()

    async def get_signals(self) -> List[Signal]:
        """
        Collect signals from all enabled strategies.
        This method fetches latest market data (ticker or OHLCV) once and passes to each strategy.
        """
        signals = []
        # Fetch latest tickers for all symbols involved
        all_symbols = set()
        for strat in self._strategies.values():
            all_symbols.update(strat.symbols)
        market_data = {}
        for sym in all_symbols:
            try:
                ticker = await self.client.fetch_ticker(sym)
                market_data[sym] = ticker
            except Exception as e:
                logger.error(f"Market data fetch error for {sym}: {e}")
        # Run each strategy's on_tick concurrently
        tasks = []
        for strat in self._strategies.values():
            if strat.enabled:
                tasks.append(strat.on_tick(market_data))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for strat, res in zip(self._strategies.values(), results):
            if isinstance(res, Exception):
                logger.error(f"Strategy {strat.name} error: {res}")
            elif res:
                signals.extend(res)
        return signals

    async def _run_loop(self):
        """Periodically call get_signals and dispatch them to the signal executor."""
        # The actual dispatch is done by the application; we can emit a callback or use a queue.
        # For Part 8, we will use a callback (set by the main app).
        while self._running:
            try:
                signals = await self.get_signals()
                if signals and self._on_signals:
                    asyncio.ensure_future(self._on_signals(signals))
            except Exception as e:
                logger.error(f"Strategy loop error: {e}")
            await asyncio.sleep(self.config.get("interval_seconds", 60))

    # Callback: set by the main application to process signals
    def set_signal_callback(self, callback):
        self._on_signals = callback