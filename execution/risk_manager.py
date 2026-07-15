"""
Risk Manager – comprehensive pre‑trade and dynamic risk controls.
"""
import asyncio
import logging
import math
import numpy as np
from datetime import datetime, date, timezone
from typing import List, Optional, Dict, Tuple
import aiosqlite

from exchange.futures_client import BinanceFuturesClient
from execution.order_executor import OrderExecutor
from execution.position_manager import PositionManager
from models.trade_request import TradeRequest
from models.position import Position
from models.exceptions import RiskLimitExceeded, TradingTerminalError
from models.risk_metrics import DailyPnL, CircuitBreakerState, RiskState
from models.notification import NotificationMessage
from utils.config import AppConfig, RiskConfig
from database import db as db_module
from utils.logger import setup_logger

logger = setup_logger(__name__)


class RiskManager:
    """
    Pre‑trade risk engine and ongoing risk state manager.
    Uses config (RiskConfig) and database for persistence.
    """

    def __init__(
        self,
        config: AppConfig,
        client: BinanceFuturesClient,
        position_manager: PositionManager,
        db_path: str = "trading_terminal.db",
    ):
        self.config = config
        self.risk_config: RiskConfig = config.risk
        self.client = client
        self.position_mgr = position_manager
        self.db_path = db_path
        self._state = RiskState()
        self._initialized = False
        self._nm = None

    async def initialize(self) -> None:
        saved = await db_module.get_risk_state(self.db_path)
        if saved:
            self._state.peak_equity = saved.get("peak_equity", 0.0)
            self._state.trading_paused = bool(saved.get("trading_paused", 0))
            self._state.pause_reason = saved.get("pause_reason")
            cb_json = saved.get("circuit_breaker_json")
            if cb_json:
                try:
                    self._state.circuit_breaker = CircuitBreakerState.parse_raw(cb_json)
                except Exception:
                    pass
        await self._ensure_schema()
        await self._update_daily_pnl()
        await self._update_drawdown()
        self._initialized = True
        logger.info("Risk Manager initialized")

    async def _ensure_schema(self):
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("ALTER TABLE risk_state ADD COLUMN circuit_breaker_json TEXT")
                await db.commit()
        except Exception:
            pass

    def set_notification_manager(self, nm):
        self._nm = nm

    async def validate_batch(
        self,
        requests: List[TradeRequest],
        total_equity: float,
        positions: Optional[List[Position]] = None,
    ) -> Tuple[bool, str]:
        if not self._initialized:
            await self.initialize()

        if self._state.trading_paused:
            return False, f"Trading paused: {self._state.pause_reason or 'external'}"

        # 1. Daily loss limit
        if self.risk_config.daily_stop_enabled:
            daily_loss = self._state.daily_pnl.net_pnl
            if daily_loss < -self.risk_config.max_daily_loss_usd:
                return False, f"Daily loss limit exceeded ({daily_loss:.2f} USD)"

        # 2. Drawdown circuit breaker
        if self.risk_config.max_drawdown_pct > 0:
            if self._state.current_drawdown_pct >= self.risk_config.max_drawdown_pct:
                return False, f"Max drawdown reached ({self._state.current_drawdown_pct:.2f}%)"

        # 3. Circuit breaker consecutive failures
        if self.risk_config.circuit_breaker.enabled:
            if self._state.circuit_breaker.triggered:
                return False, f"Circuit breaker active: {self._state.circuit_breaker.reason}"

        # 4. Exposure limits
        if positions is None:
            positions = await self.position_mgr.get_open_positions()
        ok, reason = await self._check_exposure(requests, total_equity, positions)
        if not ok:
            return False, reason

        # 5. Sector limits
        if self.risk_config.sector_limits.enabled:
            ok, reason = await self._check_sector_exposure(requests, total_equity, positions)
            if not ok:
                return False, reason

        # 6. Correlation limits
        if self.risk_config.correlation_limit.enabled:
            ok, reason = await self._check_correlation(requests, positions)
            if not ok:
                return False, reason

        # 7. Maximum leverage
        for req in requests:
            if req.leverage > self.risk_config.max_leverage:
                return False, f"Leverage {req.leverage}x exceeds max {self.risk_config.max_leverage}x for {req.symbol}"

        return True, "OK"

    async def record_trade_result(self, success: bool, pnl: float = 0.0) -> None:
        if not self._initialized:
            await self.initialize()

        cb = self.risk_config.circuit_breaker
        if cb.enabled:
            if not success:
                self._state.circuit_breaker.consecutive_failures += 1
                logger.warning(f"Consecutive failures: {self._state.circuit_breaker.consecutive_failures}")
                if self._state.circuit_breaker.consecutive_failures >= cb.max_consecutive_failures:
                    self._state.circuit_breaker.triggered = True
                    self._state.circuit_breaker.reason = f"Max failures ({cb.max_consecutive_failures})"
                    logger.error("Circuit breaker triggered!")
                    if self._nm:
                        await self._nm.notify(NotificationMessage(
                            title="Circuit Breaker Triggered",
                            body=self._state.circuit_breaker.reason,
                            level="critical",
                            category="risk"
                        ))
            else:
                self._state.circuit_breaker.consecutive_failures = 0
                if self._state.circuit_breaker.triggered:
                    self._state.circuit_breaker.triggered = False
                    logger.info("Circuit breaker reset")
            await self._persist_risk_state()

        if pnl != 0:
            self._state.daily_pnl.realized_pnl += pnl
            self._state.daily_pnl.net_pnl += pnl
            await db_module.upsert_daily_pnl(self.db_path, self._state.daily_pnl.dict())

        # Check daily loss limit and notify
        if self._nm and self.risk_config.daily_stop_enabled:
            if self._state.daily_pnl.net_pnl < -self.risk_config.max_daily_loss_usd:
                await self._nm.notify(NotificationMessage(
                    title="Daily Loss Limit Reached",
                    body=f"Daily PnL: ${self._state.daily_pnl.net_pnl:.2f} exceeded -${self.risk_config.max_daily_loss_usd}",
                    level="critical",
                    category="risk"
                ))

    async def _check_exposure(
        self, requests: List[TradeRequest], equity: float, positions: List[Position]
    ) -> Tuple[bool, str]:
        current_total_notional = sum(p.notional for p in positions)
        new_total_notional = 0.0
        symbol_exposure: Dict[str, float] = {}
        for p in positions:
            symbol_exposure[p.symbol] = symbol_exposure.get(p.symbol, 0) + p.notional

        for req in requests:
            try:
                ticker = await self.client.fetch_ticker(req.symbol)
                price = ticker["last"]
            except Exception:
                price = 0
            qty = req.quantity or (req.usd_amount / price if req.usd_amount and price else 0)
            notional = qty * price if qty else (req.usd_amount or 0)
            new_total_notional += notional
            symbol_exposure[req.symbol] = symbol_exposure.get(req.symbol, 0) + notional

        total_notional_after = current_total_notional + new_total_notional
        max_total_notional = equity * (self.risk_config.exposure.total_exposure_pct / 100.0)
        if total_notional_after > max_total_notional:
            return False, f"Total exposure {total_notional_after:.0f} exceeds max {max_total_notional:.0f}"

        max_per_sym = equity * (self.risk_config.exposure.per_symbol_exposure_pct / 100.0)
        for sym, exp in symbol_exposure.items():
            if exp > max_per_sym:
                return False, f"Exposure for {sym} ({exp:.0f}) exceeds max {max_per_sym:.0f}"
        return True, "OK"

    async def _check_sector_exposure(
        self, requests: List[TradeRequest], equity: float, positions: List[Position]
    ) -> Tuple[bool, str]:
        sector_map = self.risk_config.sector_limits.sectors
        sector_exposure: Dict[str, float] = {}
        for p in positions:
            sector = sector_map.get(p.symbol, "Other")
            sector_exposure[sector] = sector_exposure.get(sector, 0) + p.notional

        for req in requests:
            sector = sector_map.get(req.symbol, "Other")
            ticker = await self.client.fetch_ticker(req.symbol)
            price = ticker["last"]
            qty = req.quantity or (req.usd_amount / price if req.usd_amount else 0)
            notional = qty * price if qty else 0
            sector_exposure[sector] = sector_exposure.get(sector, 0) + notional

        max_sector = equity
        for sector, exp in sector_exposure.items():
            if exp > max_sector:
                return False, f"Sector {sector} exposure {exp:.0f} exceeds max {max_sector:.0f}"
        return True, "OK"

    async def _check_correlation(
        self, requests: List[TradeRequest], positions: List[Position]
    ) -> Tuple[bool, str]:
        if not positions:
            return True, "OK"
        symbols = set(p.symbol for p in positions)
        for req in requests:
            symbols.add(req.symbol)
        if len(symbols) < 2:
            return True, "OK"

        try:
            corr_matrix = await self._compute_correlation_matrix(list(symbols))
        except Exception as e:
            logger.error(f"Correlation calculation failed: {e}")
            return True, "OK"

        existing_symbols = set(p.symbol for p in positions)
        for req in requests:
            if req.symbol in existing_symbols:
                continue
            for esym in existing_symbols:
                if esym in corr_matrix and req.symbol in corr_matrix[esym]:
                    corr_val = corr_matrix[esym][req.symbol]
                    if abs(corr_val) > self.risk_config.correlation_limit.max_correlation:
                        return False, f"Correlation {req.symbol}‑{esym} {corr_val:.2f} > {self.risk_config.correlation_limit.max_correlation}"
        return True, "OK"

    async def _compute_correlation_matrix(self, symbols: List[str]) -> Dict[str, Dict[str, float]]:
        lookback = self.risk_config.correlation_limit.lookback_days
        prices = {}
        for sym in symbols:
            try:
                ohlcv = await self.client.exchange.fetch_ohlcv(sym, '1d', limit=lookback + 1)
                closes = np.array([c[4] for c in ohlcv])
                if len(closes) >= 2:
                    prices[sym] = closes
            except Exception as e:
                logger.error(f"Fetch OHLCV failed for {sym}: {e}")
        if len(prices) < 2:
            return {}

        returns = {}
        for sym, arr in prices.items():
            returns[sym] = (arr[1:] - arr[:-1]) / arr[:-1]

        sym_list = list(returns.keys())
        n = len(sym_list)
        corr_mat = np.eye(n)
        for i in range(n):
            for j in range(i + 1, n):
                try:
                    r = np.corrcoef(returns[sym_list[i]], returns[sym_list[j]])[0, 1]
                    corr_mat[i, j] = r
                    corr_mat[j, i] = r
                except Exception:
                    pass
        result = {}
        for i, si in enumerate(sym_list):
            result[si] = {}
            for j, sj in enumerate(sym_list):
                if i != j:
                    result[si][sj] = float(corr_mat[i, j])
        return result

    async def get_risk_report(self) -> Dict:
        return {
            "daily_pnl": self._state.daily_pnl.net_pnl,
            "daily_loss_limit": self.risk_config.max_daily_loss_usd,
            "drawdown_pct": self._state.current_drawdown_pct,
            "drawdown_limit_pct": self.risk_config.max_drawdown_pct,
            "trading_paused": self._state.trading_paused,
            "circuit_breaker_triggered": self._state.circuit_breaker.triggered,
        }

    async def _update_daily_pnl(self, current_equity: Optional[float] = None) -> None:
        today = date.today()
        pnl_data = await db_module.get_daily_pnl(self.db_path, today)
        if pnl_data:
            self._state.daily_pnl = DailyPnL(**pnl_data)
        else:
            self._state.daily_pnl = DailyPnL(date=today)
            await db_module.upsert_daily_pnl(self.db_path, self._state.daily_pnl.dict())

    async def _update_drawdown(self) -> None:
        rows = await db_module.get_equity_curve(self.db_path, limit=1000)
        if not rows:
            return
        equities = [r["equity"] for r in rows]
        peak = max(equities)
        self._state.peak_equity = peak
        current = equities[0]
        if peak > 0:
            drawdown = (peak - current) / peak * 100
        else:
            drawdown = 0
        self._state.current_drawdown_pct = drawdown

    async def _persist_risk_state(self) -> None:
        await db_module.save_risk_state(self.db_path, {
            "peak_equity": self._state.peak_equity,
            "trading_paused": int(self._state.trading_paused),
            "pause_reason": self._state.pause_reason,
            "circuit_breaker_json": self._state.circuit_breaker.json(),
        })

    async def pause_trading(self, reason: str = "External") -> None:
        self._state.trading_paused = True
        self._state.pause_reason = reason
        logger.warning(f"Trading paused: {reason}")
        await self._persist_risk_state()

    async def resume_trading(self) -> None:
        self._state.trading_paused = False
        self._state.pause_reason = None
        logger.info("Trading resumed")
        await self._persist_risk_state()

    async def kelly_fraction(self) -> float:
        kelly_cfg = self.risk_config.kelly
        trades = await db_module.get_completed_trades(self.db_path, min_trades=kelly_cfg.min_trades_for_calc)
        if len(trades) < kelly_cfg.min_trades_for_calc:
            win_rate = kelly_cfg.default_win_rate
            avg_win_loss = kelly_cfg.default_avg_win_loss_ratio
        else:
            win_rate = kelly_cfg.default_win_rate
            avg_win_loss = kelly_cfg.default_avg_win_loss_ratio
        if avg_win_loss <= 1:
            return 0.0
        k = (win_rate * avg_win_loss - (1 - win_rate)) / avg_win_loss
        return min(k, kelly_cfg.max_fraction)

    async def apply_volatility_scaling(self, req: TradeRequest, equity: float) -> float:
        if not self.risk_config.volatility.volatility_scaling:
            return req.quantity or 0
        atr = await self._calculate_atr(req.symbol, self.risk_config.volatility.atr_period)
        if atr <= 0:
            return req.quantity or 0
        ticker = await self.client.fetch_ticker(req.symbol)
        price = ticker["last"]
        base_qty = req.quantity or ((req.usd_amount or equity * 0.01) / price)
        target_atr = price * 0.01
        scale_factor = min(2.0, max(0.1, target_atr / atr))
        adjusted_qty = base_qty * scale_factor
        logger.debug(f"Volatility scaling: {req.symbol} ATR={atr:.2f} factor={scale_factor:.2f}")
        return adjusted_qty

    async def _calculate_atr(self, symbol: str, period: int = 14) -> float:
        try:
            ohlcv = await self.client.exchange.fetch_ohlcv(symbol, '5m', limit=period + 1)
            if len(ohlcv) < period + 1:
                return 0.0
            tr_sum = 0.0
            for i in range(1, len(ohlcv)):
                high, low = ohlcv[i][2], ohlcv[i][3]
                prev_close = ohlcv[i - 1][4]
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                tr_sum += tr
            return tr_sum / period
        except Exception:
            return 0.0