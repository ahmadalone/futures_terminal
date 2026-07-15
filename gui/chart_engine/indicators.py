"""
Indicator calculations and plotting.
"""
import numpy as np
import pyqtgraph as pg
from typing import List, Dict

class IndicatorManager:
    AVAILABLE_INDICATORS = [
        "SMA 20", "EMA 20", "Bollinger Bands", "RSI 14", "MACD", "VWAP", "ATR 14"
    ]

    def __init__(self):
        self.active: Dict[str, bool] = {}
        self.plots: Dict[str, pg.PlotDataItem] = {}
        self.price_plot = None
        self.volume_plot = None

    def set_plots(self, price_plot: pg.PlotItem, volume_plot: pg.PlotItem):
        self.price_plot = price_plot
        self.volume_plot = volume_plot

    def toggle(self, name: str):
        self.active[name] = not self.active.get(name, False)

    def is_active(self, name: str) -> bool:
        return self.active.get(name, False)

    def update(self, ohlcv: List[List[float]], symbol: str, timeframe: str):
        self._clear_plots()
        if not ohlcv:
            return
        closes = np.array([c[4] for c in ohlcv])
        highs = np.array([c[2] for c in ohlcv])
        lows = np.array([c[3] for c in ohlcv])
        volumes = np.array([c[5] for c in ohlcv])
        opens = np.array([c[1] for c in ohlcv])
        times = np.array([c[0] for c in ohlcv])

        for ind in self.AVAILABLE_INDICATORS:
            if not self.active.get(ind):
                continue
            if ind == "SMA 20":
                sma = self._sma(closes, 20)
                self._plot_on_price(times, sma, color='y', name='SMA20')
            elif ind == "EMA 20":
                ema = self._ema(closes, 20)
                self._plot_on_price(times, ema, color='c', name='EMA20')
            elif ind == "Bollinger Bands":
                sma20 = self._sma(closes, 20)
                std = np.std(closes[-20:])
                upper = sma20 + 2 * std
                lower = sma20 - 2 * std
                self._plot_on_price(times, upper, color='g', name='BB Upper', dashes=[2,2])
                self._plot_on_price(times, lower, color='g', name='BB Lower', dashes=[2,2])
                self._plot_on_price(times, sma20, color='g', name='BB Mid')
            elif ind == "RSI 14":
                rsi = self._rsi(closes, 14)
                self._plot_on_price(times, rsi, color='m', name='RSI')
            elif ind == "MACD":
                macd, signal, _ = self._macd(closes)
                self._plot_on_price(times, macd, color='y', name='MACD')
                self._plot_on_price(times, signal, color='c', name='Signal')
            elif ind == "VWAP":
                vwap = self._vwap(opens, highs, lows, closes, volumes)
                self._plot_on_price(times, vwap, color='orange', name='VWAP')
            elif ind == "ATR 14":
                atr = self._atr(highs, lows, closes, 14)
                self._plot_on_price(times, atr, color='w', name='ATR')

    def _clear_plots(self):
        for item in self.plots.values():
            self.price_plot.removeItem(item)
        self.plots.clear()

    def _plot_on_price(self, times, values, color='y', name='', **kwargs):
        curve = pg.PlotDataItem(times, values, pen=pg.mkPen(color, width=1), name=name, **kwargs)
        self.price_plot.addItem(curve)
        self.plots[name] = curve

    # --- Math helpers ---
    def _sma(self, arr, period):
        return np.convolve(arr, np.ones(period)/period, mode='same')

    def _ema(self, arr, period):
        ema = np.zeros_like(arr)
        ema[0] = arr[0]
        multiplier = 2 / (period + 1)
        for i in range(1, len(arr)):
            ema[i] = (arr[i] - ema[i-1]) * multiplier + ema[i-1]
        return ema

    def _rsi(self, closes, period):
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        rsi = np.zeros(len(closes))
        for i in range(period, len(closes)):
            avg_gain = np.mean(gains[i-period:i])
            avg_loss = np.mean(losses[i-period:i])
            if avg_loss == 0:
                rsi[i] = 100
            else:
                rs = avg_gain / avg_loss
                rsi[i] = 100 - (100 / (1 + rs))
        return rsi

    def _macd(self, closes):
        ema12 = self._ema(closes, 12)
        ema26 = self._ema(closes, 26)
        macd = ema12 - ema26
        signal = self._ema(macd, 9)
        hist = macd - signal
        return macd, signal, hist

    def _vwap(self, opens, highs, lows, closes, volumes):
        typical = (highs + lows + closes) / 3
        cumulative = np.cumsum(typical * volumes)
        cumulative_vol = np.cumsum(volumes)
        return cumulative / (cumulative_vol + 1e-9)

    def _atr(self, highs, lows, closes, period):
        tr = np.maximum(highs - lows, np.abs(highs - np.roll(closes, 1)))
        tr[0] = 0
        atr = np.zeros(len(tr))
        atr[0] = tr[0]
        for i in range(1, len(tr)):
            atr[i] = (atr[i-1] * (period-1) + tr[i]) / period
        return atr