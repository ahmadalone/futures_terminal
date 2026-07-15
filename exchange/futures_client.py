"""
Binance USDT-M Futures Client (optimized)
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any
import ccxt.pro as ccxt
from ccxt import NetworkError, ExchangeError, AuthenticationError, BadSymbol

from models.exceptions import (
    AuthenticationError as AppAuthError,
    ExchangeError as AppExchangeError,
    TradingTerminalError,
)
from utils.config import AppConfig
from optimization.cache import async_cached

logger = logging.getLogger(__name__)


class BinanceFuturesClient:
    def __init__(self, api_key: str, secret: str, testnet: bool = False):
        options = {
            "defaultType": "future",
            "adjustForTimeDifference": True,
            "recvWindow": 5000,
        }
        if testnet:
            options["urls"] = {
                "api": {
                    "public": "https://testnet.binancefuture.com/fapi/v1",
                    "private": "https://testnet.binancefuture.com/fapi/v1",
                },
                "test": {
                    "public": "https://testnet.binancefuture.com/fapi/v1",
                    "private": "https://testnet.binancefuture.com/fapi/v1",
                },
            }

        self.exchange = ccxt.binance({
            "apiKey": api_key,
            "secret": secret,
            "options": options,
            "enableRateLimit": True,
        })
        self.testnet = testnet
        self._markets_loaded = False
        self._listen_key: Optional[str] = None
        self._keep_alive_task: Optional[asyncio.Task] = None
        self._running = False
        logger.info(f"BinanceFuturesClient initialised (testnet={testnet})")

    async def load_markets(self) -> None:
        if not self._markets_loaded:
            await self.exchange.load_markets()
            self._markets_loaded = True
            logger.info("Markets loaded")

    def get_perpetual_symbols(self) -> List[str]:
        if not self._markets_loaded:
            raise TradingTerminalError("Markets not loaded. Call load_markets() first.")
        return [
            sym for sym, mkt in self.exchange.markets.items()
            if mkt.get("swap") and mkt.get("linear") and mkt.get("quote") == "USDT" and mkt.get("active")
        ]

    # ---------- Cached ticker ----------
    @async_cached(maxsize=256, ttl=1.0)
    async def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """REST ticker with 1-second cache."""
        return await self._fetch_ticker_impl(symbol)

    async def _fetch_ticker_impl(self, symbol: str) -> Dict[str, Any]:
        await self._ensure_markets_loaded()
        try:
            return await self.exchange.fetch_ticker(symbol)
        except BadSymbol:
            raise AppExchangeError(f"Invalid symbol: {symbol}")
        except Exception as e:
            raise AppExchangeError(f"fetch_ticker failed: {e}")

    # ---------- Other methods unchanged ----------
    async def watch_ticker(self, symbol: str) -> Dict[str, Any]:
        await self._ensure_markets_loaded()
        try:
            return await self.exchange.watch_ticker(symbol)
        except Exception as e:
            raise AppExchangeError(f"watch_ticker failed: {e}")

    async def watch_order_book(self, symbol: str, limit: int = 20) -> Dict[str, Any]:
        await self._ensure_markets_loaded()
        try:
            return await self.exchange.watch_order_book(symbol, limit)
        except Exception as e:
            raise AppExchangeError(f"watch_order_book failed: {e}")

    async def watch_trades(self, symbol: str) -> List[Dict[str, Any]]:
        await self._ensure_markets_loaded()
        try:
            return await self.exchange.watch_trades(symbol)
        except Exception as e:
            raise AppExchangeError(f"watch_trades failed: {e}")

    async def fetch_balance(self) -> Dict[str, Any]:
        try:
            params = {"type": "future"}
            return await self.exchange.fetch_balance(params)
        except Exception as e:
            raise AppExchangeError(f"fetch_balance failed: {e}")

    async def fetch_positions(self, symbols: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        try:
            positions = await self.exchange.fetch_positions(symbols)
            return [p for p in positions if float(p.get("contracts", 0)) != 0]
        except Exception as e:
            raise AppExchangeError(f"fetch_positions failed: {e}")

    async def fetch_open_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            return await self.exchange.fetch_open_orders(symbol)
        except Exception as e:
            raise AppExchangeError(f"fetch_open_orders failed: {e}")

    async def create_listen_key(self) -> str:
        try:
            response = await self.exchange.fapiPrivatePostListenKey()
            listen_key = response["listenKey"]
            self._listen_key = listen_key
            logger.info(f"Created listenKey: {listen_key[:8]}...")
            return listen_key
        except Exception as e:
            raise AppExchangeError(f"Failed to create listenKey: {e}")

    async def keep_alive_listen_key(self) -> bool:
        if not self._listen_key:
            logger.warning("No listenKey to keep alive")
            return False
        try:
            await self.exchange.fapiPrivatePutListenKey({
                "listenKey": self._listen_key,
            })
            logger.debug("listenKey keep-alive successful")
            return True
        except Exception as e:
            logger.error(f"listenKey keep-alive failed: {e}")
            return False

    async def close_listen_key(self) -> None:
        if not self._listen_key:
            return
        try:
            await self.exchange.fapiPrivateDeleteListenKey({
                "listenKey": self._listen_key,
            })
            logger.info("listenKey deleted")
        except Exception as e:
            logger.error(f"Failed to close listenKey: {e}")
        finally:
            self._listen_key = None

    async def _keep_alive_loop(self, interval: int = 1800) -> None:
        while self._running:
            await asyncio.sleep(interval)
            if not self._running:
                break
            success = await self.keep_alive_listen_key()
            if not success:
                logger.error("listenKey refresh failed; attempting to create a new one")
                try:
                    await self.close_listen_key()
                    await self.create_listen_key()
                    logger.info("Recreated listenKey after refresh failure")
                except Exception as e:
                    logger.exception(f"Recreate listenKey also failed: {e}")

    async def start_user_data_stream(self) -> None:
        await self.create_listen_key()
        self.exchange.options["listenKey"] = self._listen_key
        self._running = True
        self._keep_alive_task = asyncio.create_task(self._keep_alive_loop())
        logger.info("User data stream started")

    async def stop_user_data_stream(self) -> None:
        self._running = False
        if self._keep_alive_task:
            self._keep_alive_task.cancel()
            try:
                await self._keep_alive_task
            except asyncio.CancelledError:
                pass
        await self.close_listen_key()
        self.exchange.options.pop("listenKey", None)
        logger.info("User data stream stopped")

    async def watch_balance(self) -> Dict[str, Any]:
        try:
            return await self.exchange.watch_balance()
        except Exception as e:
            raise AppExchangeError(f"watch_balance failed: {e}")

    async def watch_positions(self) -> List[Dict[str, Any]]:
        try:
            return await self.exchange.watch_positions()
        except Exception as e:
            raise AppExchangeError(f"watch_positions failed: {e}")

    async def watch_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            return await self.exchange.watch_orders(symbol)
        except Exception as e:
            raise AppExchangeError(f"watch_orders failed: {e}")

    async def create_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        await self._ensure_markets_loaded()
        try:
            return await self.exchange.create_order(symbol, order_type, side, amount, price, params or {})
        except AuthenticationError:
            raise AppAuthError("Invalid API credentials")
        except ExchangeError as e:
            raise OrderExecutionError(f"Order failed: {e}") from e
        except Exception as e:
            raise AppExchangeError(f"create_order unexpected error: {e}")

    async def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        try:
            return await self.exchange.cancel_order(order_id, symbol)
        except Exception as e:
            raise AppExchangeError(f"cancel_order failed: {e}")

    async def cancel_all_orders(self, symbol: Optional[str] = None) -> None:
        try:
            await self.exchange.cancel_all_orders(symbol)
            logger.info(f"Cancelled all orders {'for ' + symbol if symbol else ''}")
        except Exception as e:
            raise AppExchangeError(f"cancel_all_orders failed: {e}")

    async def set_leverage(self, symbol: str, leverage: int) -> None:
        try:
            await self.exchange.set_leverage(leverage, symbol)
            logger.debug(f"Leverage set to {leverage}x on {symbol}")
        except Exception as e:
            raise AppExchangeError(f"set_leverage failed: {e}")

    async def set_margin_mode(self, symbol: str, mode: str) -> None:
        try:
            await self.exchange.set_margin_mode(mode, symbol)
            logger.debug(f"Margin mode set to {mode} on {symbol}")
        except Exception as e:
            raise AppExchangeError(f"set_margin_mode failed: {e}")

    async def _ensure_markets_loaded(self):
        if not self._markets_loaded:
            await self.load_markets()

    async def close(self):
        await self.stop_user_data_stream()
        try:
            await self.exchange.close()
        except Exception:
            pass