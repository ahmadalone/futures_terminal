from strategies.base import BaseStrategy
from models.signal import Signal
from typing import List
from ai.prediction_engine import PredictionEngine

class AIStrategy(BaseStrategy):
    """
    Uses the AI prediction engine to generate signals.
    """
    def __init__(self, name: str, symbols: List[str], config: dict, prediction_engine: PredictionEngine):
        super().__init__(name, symbols, config)
        self.engine = prediction_engine
        self.timeframe = config.get("timeframe", "5m")
        self.confidence_threshold = config.get("confidence_threshold", 0.6)

    async def on_tick(self, market_data: dict) -> List[Signal]:
        signals = []
        for sym in self.symbols:
            try:
                pred = await self.engine.predict(sym, self.timeframe)
                if pred.confidence >= self.confidence_threshold:
                    side = "long" if pred.direction == "up" else "short"
                    signals.append(Signal(
                        symbol=sym,
                        direction=side,
                        strength=pred.probability,
                        confidence=pred.confidence,
                        strategy_name=self.name,
                        metadata=pred.metadata
                    ))
            except Exception as e:
                logger.error(f"AI strategy predict error {sym}: {e}")
        return signals