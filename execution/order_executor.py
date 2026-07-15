import asyncio
import time
import math
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from exchange.futures_client import BinanceFuturesClient
from models.trade_request import TradeRequest, SizingMode
from models.trade_result import TradeResult
from models.exceptions import (
    OrderExecutionError,
    RiskLimitExceeded,
    InsufficientFunds,
    InvalidTradeRequest,
)
from utils.logger import setup_logger
from database.db import insert_execution

logger = setup_logger(__name__)

RETRYABLE_ERRORS = (asyncio.TimeoutError, ConnectionError, OSError)
MAX_RETRIES = 3
RETRY_BACKOFF = 0.2  # seconds, exponential

class OrderExecutor:
    """
    Low‑latency order execution engine for Binance Futures.
    Handles position sizing, leverage/margin setup, concurrent order submission,
    latency recording, retries, and database logging.
    """

    def __init__(self, client: BinanceFuturesClient, db_path: str = "trading_terminal.db"):
        self.client = client
        self.db_path = db_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def execute_orders(self, requests: List[TradeRequest]) -> List[TradeResult]:
        """
        Execute a batch of trades concurrently.
        Pre‑validates and converts sizing, then fires all orders.
        """
        if not requests:
            return []

        # Fetch account balance once for equity calculations
        balance = await self.client.fetch_balance()
        total_equity = float(balance.get("total", {}).get("USDT", 0))
        if total_equity <= 0:
            raise InsufficientFunds("Zero or negative account equity")

        # Validate and prepare tasks
        tasks = []
        for req in requests:
            self._validate_request(req)
            tasks.append(self._execute_single(req, total_equity))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        final: List[TradeResult] = []
        for req, res in zip(requests, results):
            if isinstance(res, Exception):
                logger.error(f"Execution failed for {req.symbol}: {res}")
                final.append(TradeResult(
                    symbol=req.symbol,
                    success=False,
                    message=str(res),
                    execution_timestamp=datetime.now(timezone.utc),
                ))
            else:
                final.append(res)
        return final

    async def close_position(self, symbol: str, quantity: Optional[float] = None) -> TradeResult:
        """
        Close a position: place a reduce‑only market order.
        If quantity is None, the whole position will be closed.
        """
        try:
            positions = await self.client.fetch_positions([symbol])
            pos = next((p for p in positions if p["symbol"] == symbol and float(p["contracts"]) != 0), None)
            if not pos:
                return TradeResult(symbol=symbol, success=False, message="No open position")

            side = "sell" if float(pos["contracts"]) > 0 else "buy"
            abs_qty = abs(float(pos["contracts"]))
            qty = quantity if quantity is not None else abs_qty
            req = TradeRequest(
                symbol=symbol,
                side=side,
                order_type="market",
                quantity=qty,
                reduce_only=True,
                leverage=int(pos.get("leverage", 1)),
            )
            return await self._execute_single(req, total_equity=0)  # balance not needed for closing
        except Exception as e:
            logger.exception(f"close_position failed: {e}")
            return TradeResult(symbol=symbol, success=False, message=str(e))

    async def modify_order(
        self, symbol: str, order_id: str, new_price: Optional[float] = None,
        new_quantity: Optional[float] = None
    ) -> TradeResult:
        """
        Cancel the existing order and place a new one with updated price/quantity.
        (Binance does not support direct order modification.)
        """
        try:
            # Fetch original order details
            orders = await self.client.fetch_open_orders(symbol)
            original = next((o for o in orders if o["id"] == order_id), None)
            if not original:
                return TradeResult(symbol=symbol, success=False, message="Order not found")
            # Cancel original
            await self.client.cancel_order(order_id, symbol)
            # Build new order with possibly updated params
            side = original["side"]
            order_type = original["type"]
            price = new_price if new_price is not None else original.get("price")
            amount = new_quantity if new_quantity is not None else original["amount"]
            params = original.get("params", {})
            new_order = await self.client.create_order(
                symbol, order_type, side, amount, price, params
            )
            logger.info(f"Order modified: {order_id} -> {new_order['id']}")
            return TradeResult(
                symbol=symbol,
                success=True,
                order_id=new_order["id"],
                filled_quantity=float(new_order.get("filled", 0)),
                avg_price=float(new_order.get("average", 0)) or float(new_order.get("price", 0)),
                message="Order modified",
                execution_timestamp=datetime.now(timezone.utc),
            )
        except Exception as e:
            logger.exception("modify_order failed")
            return TradeResult(symbol=symbol, success=False, message=str(e))

    async def cancel_order(self, symbol: str, order_id: str) -> TradeResult:
        try:
            await self.client.cancel_order(order_id, symbol)
            return TradeResult(symbol=symbol, success=True, message="Order cancelled")
        except Exception as e:
            return TradeResult(symbol=symbol, success=False, message=str(e))

    async def cancel_all_orders(self, symbol: Optional[str] = None) -> TradeResult:
        try:
            await self.client.cancel_all_orders(symbol)
            return TradeResult(symbol=symbol or "ALL", success=True, message="All orders cancelled")
        except Exception as e:
            return TradeResult(symbol=symbol or "ALL", success=False, message=str(e))

    # ------------------------------------------------------------------
    # Internal: per‑order execution
    # ------------------------------------------------------------------
    async def _execute_single(self, req: TradeRequest, total_equity: float) -> TradeResult:
        symbol = req.symbol
        t_start = time.monotonic()
        submit_time = datetime.now(timezone.utc)
        order_id = None
        try:
            # 1. Set leverage and margin mode
            await self.client.set_leverage(symbol, req.leverage)
            await self.client.set_margin_mode(symbol, req.margin_mode.upper())

            # 2. Calculate quantity if not explicitly given
            if req.quantity is None:
                if req.sizing_mode in ("fixed_usdt", "risk_based"):
                    ticker = await self.client.fetch_ticker(symbol)
                    price = ticker["last"]
                    req.quantity = self._calculate_quantity(req, total_equity, price)
                elif req.sizing_mode == "atr_based":
                    ticker = await self.client.fetch_ticker(symbol)
                    price = ticker["last"]
                    atr = await self._calculate_atr(symbol, period=req.atr_period)
                    req.quantity = self._calculate_atr_quantity(
                        total_equity, price, atr, req.atr_multiplier, req.usd_amount
                    )
                # else fixed_qty: already given or invalid
            if req.quantity is None:
                raise InvalidTradeRequest("Quantity could not be determined")

            # 3. Build ccxt order parameters
            params: Dict[str, Any] = {}
            if req.reduce_only:
                params["reduceOnly"] = True
            if req.order_type == "stop_market":
                if req.stop_price is None:
                    raise InvalidTradeRequest("stop_price required for stop_market orders")
                params["stopPrice"] = req.stop_price
            elif req.order_type == "stop_limit":
                if req.stop_price is None or req.price is None:
                    raise InvalidTradeRequest("stop_price and price required for stop_limit")
                params["stopPrice"] = req.stop_price
            elif req.order_type == "trailing_stop":
                if req.trailing_delta is None:
                    raise InvalidTradeRequest("trailing_delta required for trailing_stop")
                params["trailingDelta"] = req.trailing_delta

            # 4. Submit order with retries
            order = await self._retry_submit(
                symbol, req.order_type, req.side, req.quantity, req.price, params
            )
            order_id = order["id"]
            t_ack = time.monotonic()
            latency_submit = (t_ack - t_start) * 1000  # rough, actual submission timestamp not available
            latency_ack = (t_ack - t_start) * 1000

            filled = float(order.get("filled", 0))
            avg_price = float(order.get("average", 0)) or float(order.get("price", 0))

            # 5. Log to database
            await insert_execution(
                self.db_path,
                symbol=symbol,
                order_id=order_id,
                side=req.side,
                price=avg_price if filled > 0 else req.price,
                qty=filled,
                commission=None,  # commission info not always available immediately
                commission_asset=None,
                exec_type="fill" if filled > 0 else "new",
            )

            return TradeResult(
                symbol=symbol,
                success=True,
                order_id=order_id,
                message="Filled" if filled > 0 else "Accepted",
                execution_timestamp=submit_time,
                latency_submit_ms=latency_submit,
                latency_ack_ms=latency_ack,
                filled_quantity=filled,
                avg_price=avg_price,
            )
        except Exception as e:
            logger.exception(f"Order execution exception for {symbol}")
            return TradeResult(
                symbol=symbol,
                success=False,
                order_id=order_id,
                message=f"Execution error: {str(e)}",
                execution_timestamp=submit_time,
            )

    # ------------------------------------------------------------------
    # Position sizing helpers
    # ------------------------------------------------------------------
    def _calculate_quantity(self, req: TradeRequest, equity: float, current_price: float) -> float:
        """Compute contract quantity based on sizing_mode."""
        mode: SizingMode = req.sizing_mode
        if mode == "fixed_usdt":
            if req.usd_amount is None:
                raise InvalidTradeRequest("usd_amount required for fixed_usdt sizing")
            return req.usd_amount / current_price
        elif mode == "percent_equity":
            # No separate percentage field, assume usd_amount is percentage (0.0-100.0) if used
            if req.usd_amount is None:
                raise InvalidTradeRequest("usd_amount required for percent_equity (in % of equity)")
            risk_capital = equity * (req.usd_amount / 100.0)
            return risk_capital / current_price
        elif mode == "risk_based":
            # Risk based on stop loss percentage
            if req.stop_loss_pct is None or req.usd_amount is None:
                raise InvalidTradeRequest("stop_loss_pct and usd_amount required for risk_based sizing")
            risk_capital = equity * (req.usd_amount / 100.0)  # risk per trade as % of equity
            stop_distance = current_price * (req.stop_loss_pct / 100.0)
            if stop_distance <= 0:
                raise InvalidTradeRequest("stop_loss_pct must be > 0")
            return risk_capital / stop_distance
        elif mode == "fixed_qty":
            if req.quantity is None:
                raise InvalidTradeRequest("quantity required for fixed_qty sizing")
            return req.quantity
        else:
            raise InvalidTradeRequest(f"Unknown sizing mode: {mode}")

    def _calculate_atr_quantity(
        self, equity: float, price: float, atr: float, multiplier: float,
        risk_usd_percent: Optional[float] = None
    ) -> float:
        """Position size where stop distance = multiplier * ATR, risk = risk_usd_percent of equity."""
        if risk_usd_percent is None or risk_usd_percent <= 0:
            raise InvalidTradeRequest("risk_usd_percent required for ATR sizing")
        risk_capital = equity * (risk_usd_percent / 100.0)
        stop_distance = multiplier * atr
        if stop_distance <= 0:
            raise InvalidTradeRequest("ATR stop distance is zero")
        return risk_capital / stop_distance

    async def _calculate_atr(self, symbol: str, period: int = 14, timeframe: str = "5m") -> float:
        """Fetch recent OHLCV and compute ATR."""
        try:
            ohlcv = await self.client.exchange.fetch_ohlcv(symbol, timeframe, limit=period + 1)
            if len(ohlcv) < period + 1:
                return 0.0
            tr_sum = 0.0
            for i in range(1, len(ohlcv)):
                high = ohlcv[i][2]
                low = ohlcv[i][3]
                prev_close = ohlcv[i - 1][4]
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                tr_sum += tr
            return tr_sum / period
        except Exception as e:
            logger.warning(f"ATR calculation failed for {symbol}: {e}")
            return 0.0

    # ------------------------------------------------------------------
    # Validation & retry
    # ------------------------------------------------------------------
    def _validate_request(self, req: TradeRequest) -> None:
        if not self.client.exchange.markets.get(req.symbol):
            raise InvalidTradeRequest(f"Unknown symbol: {req.symbol}")
        if req.side not in ("buy", "sell"):
            raise InvalidTradeRequest("side must be 'buy' or 'sell'")

    async def _retry_submit(
        self, symbol: str, order_type: str, side: str, amount: float,
        price: Optional[float], params: dict
    ) -> dict:
        """Submit order with exponential backoff on transient errors."""
        last_exc = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                return await self.client.create_order(symbol, order_type, side, amount, price, params)
            except RETRYABLE_ERRORS as e:
                last_exc = e
                if attempt < MAX_RETRIES:
                    wait = RETRY_BACKOFF * (2 ** attempt)
                    logger.warning(f"Retry {attempt+1}/{MAX_RETRIES} after {wait:.2f}s: {e}")
                    await asyncio.sleep(wait)
            except Exception as e:
                # Non‑retryable, re‑raise immediately
                raise OrderExecutionError(f"Order submission failed: {e}") from e
        raise OrderExecutionError(f"Order submission failed after {MAX_RETRIES} retries: {last_exc}")