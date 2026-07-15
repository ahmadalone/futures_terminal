import os
import yaml
from pathlib import Path
from pydantic import BaseModel, Field, ValidationError
from typing import Optional, Dict, Any, List, Literal
from dotenv import load_dotenv

load_dotenv()

# ----------------------------------------------------------------------
# Database / Logging / GUI
# ----------------------------------------------------------------------
class DatabaseConfig(BaseModel):
    path: str = "trading_terminal.db"

class LoggingConfig(BaseModel):
    level: str = "DEBUG"
    file: str = "logs/terminal.log"
    max_bytes: int = 10485760
    backup_count: int = 5
    format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt: str = "%Y-%m-%d %H:%M:%S"

class DefaultsConfig(BaseModel):
    leverage: int = 1
    max_position_usd: float = 10000
    max_risk_per_trade_pct: float = 1.0
    daily_loss_limit_usd: float = 500.0
    max_concurrent_positions: int = 10

class GUIConfig(BaseModel):
    dark_mode: bool = True
    refresh_interval_ms: int = 500

# ----------------------------------------------------------------------
# Risk Engine
# ----------------------------------------------------------------------
class CircuitBreakerConfig(BaseModel):
    enabled: bool = True
    max_consecutive_failures: int = 5

class ExposureConfig(BaseModel):
    total_exposure_pct: float = 300.0
    per_symbol_exposure_pct: float = 100.0

class SectorLimitsConfig(BaseModel):
    enabled: bool = True
    sectors: Dict[str, str] = Field(default_factory=dict)

class CorrelationLimitConfig(BaseModel):
    enabled: bool = True
    max_correlation: float = 0.8
    lookback_days: int = 7

class KellyConfig(BaseModel):
    enabled: bool = True
    max_fraction: float = 0.5
    min_trades_for_calc: int = 20
    default_win_rate: float = 0.55
    default_avg_win_loss_ratio: float = 1.5

class VolatilityConfig(BaseModel):
    enabled: bool = True
    atr_period: int = 14
    atr_multiplier: float = 2.0
    volatility_scaling: bool = True

class NewsProtectionConfig(BaseModel):
    enabled: bool = True

class RiskConfig(BaseModel):
    max_daily_loss_usd: float = 500.0
    max_drawdown_pct: float = 20.0
    daily_stop_enabled: bool = True
    circuit_breaker: CircuitBreakerConfig = Field(default_factory=CircuitBreakerConfig)
    exposure: ExposureConfig = Field(default_factory=ExposureConfig)
    sector_limits: SectorLimitsConfig = Field(default_factory=SectorLimitsConfig)
    correlation_limit: CorrelationLimitConfig = Field(default_factory=CorrelationLimitConfig)
    max_leverage: int = 20
    kelly: KellyConfig = Field(default_factory=KellyConfig)
    volatility: VolatilityConfig = Field(default_factory=VolatilityConfig)
    news_protection: NewsProtectionConfig = Field(default_factory=NewsProtectionConfig)

# ----------------------------------------------------------------------
# Strategies
# ----------------------------------------------------------------------
class StrategiesConfig(BaseModel):
    active: List[str] = []
    params: Dict[str, dict] = {}
    interval_seconds: int = 60
    allocation: dict = Field(default_factory=lambda: {"method": "equal", "max_allocation_pct": 20})

# ----------------------------------------------------------------------
# Notifications
# ----------------------------------------------------------------------
class TelegramConfig(BaseModel):
    enabled: bool = False
    bot_token: str = ""
    chat_id: str = ""

class DiscordConfig(BaseModel):
    enabled: bool = False
    webhook_url: str = ""

class EmailConfig(BaseModel):
    enabled: bool = False
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    username: str = ""
    password: str = ""
    recipient: str = ""

class DesktopConfig(BaseModel):
    enabled: bool = True

class TradeAlertConfig(BaseModel):
    enabled: bool = True
    min_pnl_usd: float = 10.0

class RiskAlertConfig(BaseModel):
    enabled: bool = True
    daily_loss_pct: float = 5.0

class DailyReportConfig(BaseModel):
    enabled: bool = True
    time: str = "23:59"

class NotificationsConfig(BaseModel):
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    desktop: DesktopConfig = Field(default_factory=DesktopConfig)
    trade_alert: TradeAlertConfig = Field(default_factory=TradeAlertConfig)
    risk_alert: RiskAlertConfig = Field(default_factory=RiskAlertConfig)
    daily_report: DailyReportConfig = Field(default_factory=DailyReportConfig)

# ----------------------------------------------------------------------
# AI
# ----------------------------------------------------------------------
class AIModelConfig(BaseModel):
    name: str
    type: Literal["xgboost", "lightgbm", "lstm"]
    params: dict = {}
    input_size: Optional[int] = None
    load_version: Optional[str] = None

class AIConfig(BaseModel):
    models: List[AIModelConfig] = []
    online_learning: dict = Field(default_factory=lambda: {"interval_hours": 1, "symbols": []})

# ----------------------------------------------------------------------
# Backtesting
# ----------------------------------------------------------------------
class BacktestingConfig(BaseModel):
    initial_equity: float = 10000
    fee_rate: float = 0.0004
    slippage_pct: float = 0.0005
    cache_dir: str = "data/historical"
    default_timeframe: str = "5m"

# ----------------------------------------------------------------------
# Plugins
# ----------------------------------------------------------------------
class PluginsConfig(BaseModel):
    directories: List[str] = ["plugins"]
    auto_load: bool = True

# ----------------------------------------------------------------------
# Top‑level AppConfig
# ----------------------------------------------------------------------
class AppConfig(BaseModel):
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    exchange: Dict[str, Any] = Field(default_factory=dict)
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    gui: GUIConfig = Field(default_factory=GUIConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    notifications: NotificationsConfig = Field(default_factory=NotificationsConfig)
    strategies: StrategiesConfig = Field(default_factory=StrategiesConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    backtesting: BacktestingConfig = Field(default_factory=BacktestingConfig)
    plugins: PluginsConfig = Field(default_factory=PluginsConfig)

    @classmethod
    def from_yaml(cls, path: str = "config.yaml") -> "AppConfig":
        if not Path(path).exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        with open(path, "r") as f:
            raw = f.read()
        raw = os.path.expandvars(raw)
        data = yaml.safe_load(raw)
        try:
            return cls(**data)
        except ValidationError as e:
            raise ValueError(f"Invalid configuration: {e}") from e

def load_config() -> AppConfig:
    return AppConfig.from_yaml()