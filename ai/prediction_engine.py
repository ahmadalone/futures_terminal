"""
Orchestrates feature generation, model prediction, ensemble, and confidence scoring.
"""
import asyncio
from typing import Dict, Optional, List
import numpy as np
from exchange.futures_client import BinanceFuturesClient
from ai.feature_engine import FeatureEngine
from ai.model_manager import BaseModel, XGBoostModel, LightGBMModel, PyTorchBaseModel
from ai.prediction_models import Prediction
from utils.logger import setup_logger

logger = setup_logger(__name__)

class PredictionEngine:
    """
    Main interface for AI predictions. Manages models and generates forecasts.
    """
    def __init__(self, client: BinanceFuturesClient, config: dict):
        self.client = client
        self.feature_engine = FeatureEngine(client)
        self.models: Dict[str, BaseModel] = {}
        self.config = config
        self.ensemble_weights: Dict[str, float] = {}  # model_name -> weight (based on performance)
        self._init_models()

    def _init_models(self):
        # Initialize models listed in config
        model_cfgs = self.config.get("models", [])
        for cfg in model_cfgs:
            name = cfg["name"]
            model_type = cfg["type"]
            if model_type == "xgboost":
                self.models[name] = XGBoostModel(name, params=cfg.get("params"))
            elif model_type == "lightgbm":
                self.models[name] = LightGBMModel(name, params=cfg.get("params"))
            elif model_type == "lstm":
                input_size = cfg.get("input_size", 20)  # number of features
                self.models[name] = PyTorchBaseModel(name, input_size, model_type="lstm")
            # Load pretrained if path given
            if "load_version" in cfg:
                try:
                    self.models[name].load(cfg["load_version"])
                except Exception as e:
                    logger.error(f"Could not load {name}: {e}")

        # Ensemble weights (default equal)
        self.ensemble_weights = {name: 1.0/len(self.models) for name in self.models}

    async def predict(self, symbol: str, timeframe: str = "5m") -> Prediction:
        """
        Generate a single prediction for the latest data point.
        Returns a Prediction with direction, probability, confidence.
        """
        # Get latest features
        try:
            df = await self.feature_engine.compute_features(symbol, timeframe, lookback=200)
            if df.empty:
                raise ValueError("No features generated")
            # Use last row (most recent) for prediction
            last_features = df.iloc[-1:].drop(columns=["target"]).values
        except Exception as e:
            logger.error(f"Feature generation failed: {e}")
            return Prediction(symbol=symbol, direction="up", probability=0.5, confidence=0.0, model_name="none")

        # Collect predictions from all models
        model_preds = {}
        for name, model in self.models.items():
            try:
                prob = model.predict_proba(last_features)[0]
                model_preds[name] = prob
            except Exception as e:
                logger.error(f"Model {name} failed: {e}")

        if not model_preds:
            return Prediction(symbol=symbol, direction="up", probability=0.5, confidence=0.0, model_name="none")

        # Weighted ensemble probability
        ensemble_prob = 0.0
        total_weight = 0.0
        for name, prob in model_preds.items():
            w = self.ensemble_weights.get(name, 0.0)
            ensemble_prob += prob * w
            total_weight += w
        if total_weight > 0:
            ensemble_prob /= total_weight
        else:
            ensemble_prob = 0.5

        direction = "up" if ensemble_prob > 0.5 else "down"
        # Confidence based on agreement of models
        agreement = np.std(list(model_preds.values()))
        confidence = 1.0 - min(agreement * 5, 1.0)  # lower std -> higher confidence
        # Adjust with model historical accuracy (simplified: use weight as proxy)
        confidence *= max(self.ensemble_weights.values()) if self.ensemble_weights else 0.5

        return Prediction(
            symbol=symbol,
            direction=direction,
            probability=float(ensemble_prob),
            confidence=float(confidence),
            model_name="ensemble",
            metadata={"model_preds": model_preds}
        )

    async def train_models(self, symbol: str, timeframe: str = "5m", lookback_days: int = 7):
        """
        Train all models on historical data for the given symbol.
        """
        df = await self.feature_engine.compute_features(symbol, timeframe, lookback=lookback_days*288)  # approx
        if df.empty:
            return
        feature_cols = [c for c in df.columns if c != "target"]
        X = df[feature_cols].values
        y = df["target"].values

        for name, model in self.models.items():
            try:
                model.train(X, y)
                model.save()
                logger.info(f"Trained and saved {name} for {symbol}")
            except Exception as e:
                logger.error(f"Training failed for {name}: {e}")

    def update_ensemble_weights(self, performance_metrics: Dict[str, float]):
        """
        Update model weights based on recent Sharpe ratios or accuracy.
        """
        total = sum(performance_metrics.values())
        if total > 0:
            self.ensemble_weights = {k: v/total for k, v in performance_metrics.items()}