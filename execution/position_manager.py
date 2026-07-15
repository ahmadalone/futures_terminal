"""
Position Manager – monitors, calculates metrics, and handles partial closes,
scaling, trailing stops, emergency exit.
"""
import asyncio
import math
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from exchange.futures_client import BinanceFuturesClient
from execution.order_executor import OrderExecutor
from models.position import Position
from models.trade_request import TradeRequest
from models.trade_result import TradeResult
from models.exceptions import PositionError, TradingTerminalError
from utils.logger import setup_logger
from database.db import insert_position_snapshot

logger = setup_logger(__name__)


class PositionManager:
    def __init__(
        self,
        client: BinanceFuturesClient,
        executor: OrderExecutor,
        db_path: str = "trading_terminal.db",
    ):
        self.client = client
        self.executor = executor
        self.db_path = db_path

    # ------------------------------------------------------------------
    # Core
    # ------------------------------------------------------------------
    async def get_open_positions(self) -> List[Position]:
        """Retrieve and enrich all current open positions from the exchange."""
        raw_positions = await self.client.fetch_positions()
        enriched = []
        for rp in raw_positions:
            pos = await self._build_position(rp)
            enriched.append(pos)
            # Persist snapshot
            await insert_position_snapshot(self.db_path, pos.dict())
        return enriched

    async def get_position(self, symbol: str) -> Optional[Position]:
        """Return a single position for a symbol, or None."""
        positions = await self.get_open_positions()
        for p in positions:
            if p.symbol == symbol:
                return p
        return None

    # ------------------------------------------------------------------
    # Metric helpers (standalone)
    # ------------------------------------------------------------------
    async def calculate_metrics(self, symbol: str) -> Dict[str, Any]:
        """Return a dict of all key risk/performance metrics for a symbol."""
        pos = await self.get_position(symbol)
        if not pos:
            raise PositionError(f"No open position for {symbol}")
        return {
            "symbol": symbol,
            "pnl": pos.unrealized_pnl,
            "roe_pct": pos.roe,
            "liquidation_price": pos.liquidation_price,
            "liquidation_distance_pct": pos.liquidation_distance_pct,
            "break_even_price": pos.break_even_price,
            "margin_ratio": pos.margin_ratio,
            "funding_rate": pos.funding_rate,
            "funding_fee": pos.funding_fee,
            "notional": pos.notional,
            "leverage": pos.leverage,
        }

    # ------------------------------------------------------------------
    # Position adjustment
    # ------------------------------------------------------------------
    async def partial_close(self, symbol: str, percentage: float) -> TradeResult:
        """
        Close a percentage of the current position (reduce‑only).
        percentage is expressed as 0.0 – 100.0.
        """
        pos = await self.get_position(symbol)
        if not pos:
            raise PositionError(f"No open position for {symbol}")
        qty_to_close = (abs(pos.quantity) * percentage) / 100.0
        if qty_to_close <= 0:
            return TradeResult(symbol=symbol, success=False, message="Zero quantity")
        side = "sell" if pos.side == "long" else "buy"
        req = TradeRequest(
            symbol=symbol,
            side=side,
            order_type="market",
            quantity=qty_to_close,
            reduce_only=True,
            leverage=pos.leverage,
        )
        result = await self.executor.execute_orders([req])
        return result[0]

    async def scale_in(self, symbol: str, usd_amount: float) -> TradeResult:
        """
        Add to an existing position using a market order.
        The direction is automatically inferred from the current position.
        """
        pos = await self.get_position(symbol)
        if not pos:
            # No position – simply open a new one (buy for long)
            side = "buy"  # default to long; caller should be explicit if needed
        else:
            side = "buy" if pos.side == "long" else "sell"
        req = TradeRequest(
            symbol=symbol,
            side=side,
            order_type="market",
            usd_amount=usd_amount,
            sizing_mode="fixed_usdt",
            leverage=pos.leverage if pos else 1,
        )
        return await self.executor.execute_orders([req])[0]

    async def scale_out(self, symbol: str, percentage: float) -> TradeResult:
        """Same as partial_close, retained for semantic clarity."""
        return await self.partial_close(symbol, percentage)

    # ------------------------------------------------------------------
    # Trailing stop
    # ------------------------------------------------------------------
    async def update_trailing_stop(
        self,
        symbol: str,
        activation_price: float,
        trailing_delta: float,
    ) -> TradeResult:
        """
        Place a trailing stop order. For simplicity, we submit a new
        trailing stop order (which will replace any existing one if needed).
        Requires the exchange to support trailingDelta parameter.
        """
        pos = await self.get_position(symbol)
        if not pos:
            raise PositionError(f"No position to attach trailing stop: {symbol}")
        # Cancel any existing stop orders for this symbol
        await self.client.cancel_all_orders(symbol)

        side = "sell" if pos.side == "long" else "buy"
        req = TradeRequest(
            symbol=symbol,
            side=side,
            order_type="trailing_stop",
            quantity=abs(pos.quantity),        # full position
            reduce_only=True,
            trailing_delta=trailing_delta,
            # activation_price is not directly supported; we can approximate
            # by setting stop price (but trailing stop ignores it). We'll pass it as note.
            # Some exchanges support activationPrice, but Binance uses trailingDelta only.
            # We will use a simple approach: place a trailing stop with trailingDelta.
        )
        # Binance trailing stop uses trailingDelta as the distance from the market
        # If we need activation, we could place a stop market first, but trailing stop
        # works immediately. We'll ignore activation_price for simplicity.
        return await self.executor.execute_orders([req])[0]

    # ------------------------------------------------------------------
    # Emergency exit
    # ------------------------------------------------------------------
    async def emergency_close_all(self) -> List[TradeResult]:
        """
        Close every open position regardless of PnL, using market orders.
        This is the "panic button".
        """
        positions = await self.get_open_positions()
        if not positions:
            logger.info("No positions to close")
            return []
        requests = []
        for pos in positions:
            side = "sell" if pos.side == "long" else "buy"
            requests.append(TradeRequest(
                symbol=pos.symbol,
                side=side,
                order_type="market",
                quantity=abs(pos.quantity),
                reduce_only=True,
                leverage=pos.leverage,
            ))
        logger.warning(f"Emergency closing {len(requests)} positions")
        return await self.executor.execute_orders(requests)

    # ------------------------------------------------------------------
    # Auto-hedge (simple) – open an equal-sized opposite position
    # ------------------------------------------------------------------
    async def auto_hedge(self, symbol: str) -> TradeResult:
        """
        Open a hedge: if long, open a short with the same notional value.
        Uses the current position's notional.
        """
        pos = await self.get_position(symbol)
        if not pos:
            raise PositionError(f"No position to hedge: {symbol}")
        side = "sell" if pos.side == "long" else "buy"
        req = TradeRequest(
            symbol=symbol,
            side=side,
            order_type="market",
            usd_amount=pos.notional,
            sizing_mode="fixed_usdt",
            leverage=pos.leverage,
            # Do NOT set reduce_only; we want a new position
        )
        return await self.executor.execute_orders([req])[0]

    # ------------------------------------------------------------------
    # Synchronization: update local DB with latest exchange data
    # ------------------------------------------------------------------
    async def synchronize(self) -> List[Position]:
        """Full sync: fetch positions, update DB, return them."""
        positions = await self.get_open_positions()
        logger.info(f"Synchronized {len(positions)} positions")
        return positions

    # ------------------------------------------------------------------
    # Internal: build a Position model from ccxt position dict
    # ------------------------------------------------------------------
    async def _build_position(self, raw: Dict[str, Any]) -> Position:
        symbol = raw["symbol"]
        contracts = float(raw.get("contracts", 0))
        side = "long" if contracts > 0 else "short"
        qty = abs(contracts)
        entry_price = float(raw.get("entryPrice", 0))
        mark_price = float(raw.get("markPrice", 0))
        liquidation_price = float(raw.get("liquidationPrice", 0)) if raw.get("liquidationPrice") else None
        leverage = int(raw.get("leverage", 1))
        unrealized_pnl = float(raw.get("unrealizedPnl", 0))
        margin = float(raw.get("initialMargin", 0))
        notional = float(raw.get("notional", 0))
        roe = (unrealized_pnl / margin * 100) if margin != 0 else 0.0

        # Break-even
        taker_fee = 0.0004  # approximate Binance taker fee; could be fetched from exchange
        break_even = None
        if entry_price and qty > 0:
            # break-even = entry * (1 + 2*fee) for long; for short: entry * (1 - 2*fee)
            factor = 1 + 2 * taker_fee if side == "long" else 1 - 2 * taker_fee
            break_even = entry_price * factor

        # Liquidation distance %
        liq_dist = None
        if liquidation_price and mark_price:
            if side == "long":
                liq_dist = abs(1 - (liquidation_price / mark_price)) * 100
            else:
                liq_dist = abs(1 - (mark_price / liquidation_price)) * 100 if liquidation_price != 0 else None

        # Margin ratio (maintenance margin % of notional)
        maint_margin_rate = 0.005  # typical 0.5% for BTC; could be dynamic
        margin_ratio = (maint_margin_rate * notional) / margin if margin > 0 else None

        # Funding rate (next rate from exchange; we need a separate call)
        funding_rate = None
        funding_fee = None
        try:
            funding_info = await self.client.exchange.fetch_funding_rate(symbol)
            funding_rate = float(funding_info.get("fundingRate", 0))
            # Estimated next funding payment: notional * funding_rate
            if funding_rate:
                funding_fee = notional * funding_rate
        except Exception:
            logger.debug(f"Could not fetch funding rate for {symbol}")

        return Position(
            symbol=symbol,
            side=side,
            quantity=qty,
            entry_price=entry_price,
            mark_price=mark_price,
            liquidation_price=liquidation_price,
            leverage=leverage,
            unrealized_pnl=unrealized_pnl,
            margin=margin,
            notional=notional,
            roe=roe,
            break_even_price=break_even,
            margin_ratio=margin_ratio,
            funding_rate=funding_rate,
            funding_fee=funding_fee,
            liquidation_distance_pct=liq_dist,
            last_update=datetime.now(timezone.utc),
        )