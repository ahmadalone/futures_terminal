"""
Online learning / periodic retraining scheduler.
"""
import asyncio
from ai.prediction_engine import PredictionEngine
from utils.logger import setup_logger

logger = setup_logger(__name__)

class OnlineLearner:
    def __init__(self, engine: PredictionEngine, interval_hours: int = 1):
        self.engine = engine
        self.interval = interval_hours * 3600
        self._task = None

    async def start(self, symbols: list, timeframe: str = "5m"):
        """Begin periodic retraining for the given symbols."""
        self._task = asyncio.create_task(self._run(symbols, timeframe))

    async def stop(self):
        if self._task:
            self._task.cancel()

    async def _run(self, symbols, timeframe):
        while True:
            for sym in symbols:
                try:
                    await self.engine.train_models(sym, timeframe)
                except Exception as e:
                    logger.error(f"Online learner error for {sym}: {e}")
            await asyncio.sleep(self.interval)