"""Custom exceptions for the trading terminal."""

class TradingTerminalError(Exception):
    """Base exception for the application."""

class ConfigurationError(TradingTerminalError):
    """Raised when configuration is invalid."""

class ExchangeError(TradingTerminalError):
    """General exchange-related error."""

class AuthenticationError(ExchangeError):
    """Authentication failure with the exchange."""

class OrderExecutionError(ExchangeError):
    """Order could not be executed."""

class RiskLimitExceeded(TradingTerminalError):
    """Trade would violate a risk limit."""

class InsufficientFunds(TradingTerminalError):
    """Not enough balance/margin."""

class InvalidTradeRequest(TradingTerminalError):
    """Trade request parameters are invalid."""

class PositionError(TradingTerminalError):
    """Error related to position management."""

class PluginError(TradingTerminalError):
    """Error in plugin loading or execution."""

class BacktestError(TradingTerminalError):
    """Error during backtesting."""