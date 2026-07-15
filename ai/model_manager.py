"""
ML model implementations: LSTM, Transformer, XGBoost, LightGBM.
Unified interface for training, prediction, saving, and loading.
"""
import os
import json
from abc import ABC, abstractmethod
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
import numpy as np
import pandas as pd
import joblib

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import lightgbm as lgb

from utils.logger import setup_logger

logger = setup_logger(__name__)

# ----------------------------------------------------------------------
# Base model
# ----------------------------------------------------------------------
class BaseModel(ABC):
    def __init__(self, name: str, model_dir: str = "ai/models"):
        self.name = name
        self.model_dir = Path(model_dir) / name
        self.model_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def train(self, X: np.ndarray, y: np.ndarray, **kwargs):
        ...

    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray:
        ...

    @abstractmethod
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        ...

    def save(self, version: str = None):
        pass

    def load(self, version: str = None):
        pass


# ----------------------------------------------------------------------
# PyTorch LSTM Classifier
# ----------------------------------------------------------------------
class LSTMModel(nn.Module):
    def __init__(self, input_size, hidden_size=64, num_layers=2, dropout=0.2):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True, dropout=dropout)
        self.fc = nn.Linear(hidden_size, 1)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        out, _ = self.lstm(x)
        out = out[:, -1, :]  # last time step
        out = self.fc(out)
        return self.sigmoid(out)

class PyTorchBaseModel(BaseModel):
    def __init__(self, name, input_size, model_type="lstm", **kwargs):
        super().__init__(name)
        self.input_size = input_size
        self.model_type = model_type
        self.kwargs = kwargs
        self.model = None
        self.scaler = StandardScaler()
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def train(self, X, y, epochs=20, batch_size=64, lr=0.001):
        X_scaled = self.scaler.fit_transform(X)
        y = np.array(y).reshape(-1, 1)
        # For LSTM, we need shape (samples, seq_len, features). X is already 2D; assume each row is a time step.
        # We'll create sequences later. For simplicity, we'll treat each row as a single time step (seq_len=1).
        # More advanced: split into sliding windows. We'll accept sequences externally.
        # For now, we'll reshape to (n, 1, features) for LSTM.
        X_reshaped = X_scaled.reshape(X_scaled.shape[0], 1, X_scaled.shape[1])
        X_tensor = torch.FloatTensor(X_reshaped).to(self.device)
        y_tensor = torch.FloatTensor(y).to(self.device)

        if self.model is None:
            if self.model_type == "lstm":
                self.model = LSTMModel(input_size=self.input_size, **self.kwargs)
            # Add transformer later
            self.model.to(self.device)

        dataset = TensorDataset(X_tensor, y_tensor)
        loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
        optimizer = optim.Adam(self.model.parameters(), lr=lr)
        criterion = nn.BCELoss()

        self.model.train()
        for epoch in range(epochs):
            total_loss = 0
            for bx, by in loader:
                optimizer.zero_grad()
                preds = self.model(bx)
                loss = criterion(preds, by)
                loss.backward()
                optimizer.step()
                total_loss += loss.item()
            logger.debug(f"{self.name} epoch {epoch+1}/{epochs} loss: {total_loss/len(loader):.4f}")

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        X_scaled = self.scaler.transform(X)
        X_reshaped = X_scaled.reshape(X_scaled.shape[0], 1, X_scaled.shape[1])
        X_tensor = torch.FloatTensor(X_reshaped).to(self.device)
        self.model.eval()
        with torch.no_grad():
            prob = self.model(X_tensor).cpu().numpy()
        return prob.flatten()

    def predict(self, X: np.ndarray) -> np.ndarray:
        return (self.predict_proba(X) > 0.5).astype(int)

    def save(self, version: str = None):
        version = version or datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = self.model_dir / f"{version}.pth"
        torch.save({
            'model_state': self.model.state_dict(),
            'scaler': self.scaler
        }, path)
        logger.info(f"Saved {self.name} model to {path}")

    def load(self, version: str = None):
        if version is None:
            versions = sorted(self.model_dir.glob("*.pth"))
            if not versions:
                raise FileNotFoundError(f"No saved models for {self.name}")
            path = versions[-1]
        else:
            path = self.model_dir / f"{version}.pth"
        checkpoint = torch.load(path, map_location=self.device)
        if self.model is None:
            self.model = LSTMModel(input_size=self.input_size, **self.kwargs)
        self.model.load_state_dict(checkpoint['model_state'])
        self.model.to(self.device)
        self.scaler = checkpoint['scaler']
        logger.info(f"Loaded {self.name} model from {path}")

# ----------------------------------------------------------------------
# XGBoost model
# ----------------------------------------------------------------------
class XGBoostModel(BaseModel):
    def __init__(self, name, params=None):
        super().__init__(name)
        self.params = params or {'objective': 'binary:logistic', 'eval_metric': 'logloss', 'max_depth': 5, 'eta': 0.1}
        self.model = None
        self.scaler = StandardScaler()

    def train(self, X, y, **kwargs):
        X_scaled = self.scaler.fit_transform(X)
        dtrain = xgb.DMatrix(X_scaled, label=y)
        self.model = xgb.train(self.params, dtrain, num_boost_round=kwargs.get('num_boost_round', 100))

    def predict_proba(self, X):
        X_scaled = self.scaler.transform(X)
        dtest = xgb.DMatrix(X_scaled)
        return self.model.predict(dtest)

    def predict(self, X):
        return (self.predict_proba(X) > 0.5).astype(int)

    def save(self, version=None):
        version = version or datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = self.model_dir / f"{version}.pkl"
        with open(path, 'wb') as f:
            joblib.dump({'model': self.model, 'scaler': self.scaler}, f)

    def load(self, version=None):
        if version is None:
            versions = sorted(self.model_dir.glob("*.pkl"))
            if not versions:
                raise FileNotFoundError(f"No saved models for {self.name}")
            path = versions[-1]
        else:
            path = self.model_dir / f"{version}.pkl"
        data = joblib.load(path)
        self.model = data['model']
        self.scaler = data['scaler']

# ----------------------------------------------------------------------
# LightGBM model
# ----------------------------------------------------------------------
class LightGBMModel(BaseModel):
    def __init__(self, name, params=None):
        super().__init__(name)
        self.params = params or {'objective': 'binary', 'metric': 'binary_logloss', 'boosting_type': 'gbdt', 'num_leaves': 31}
        self.model = None
        self.scaler = StandardScaler()

    def train(self, X, y, **kwargs):
        X_scaled = self.scaler.fit_transform(X)
        dtrain = lgb.Dataset(X_scaled, label=y)
        self.model = lgb.train(self.params, dtrain, num_boost_round=kwargs.get('num_boost_round', 100))

    def predict_proba(self, X):
        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)

    def predict(self, X):
        return (self.predict_proba(X) > 0.5).astype(int)

    def save(self, version=None):
        version = version or datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = self.model_dir / f"{version}.pkl"
        with open(path, 'wb') as f:
            joblib.dump({'model': self.model, 'scaler': self.scaler}, f)

    def load(self, version=None):
        if version is None:
            versions = sorted(self.model_dir.glob("*.pkl"))
            if not versions:
                raise FileNotFoundError(f"No saved models for {self.name}")
            path = versions[-1]
        else:
            path = self.model_dir / f"{version}.pkl"
        data = joblib.load(path)
        self.model = data['model']
        self.scaler = data['scaler']