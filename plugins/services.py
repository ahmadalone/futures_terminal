"""
ServiceRegistry – provides typed access to core terminal services for plugins.
"""
from exchange.futures_client import BinanceFuturesClient
from notifications.manager import NotificationManager
from execution.risk_manager import RiskManager
from execution.position_manager import PositionManager
from execution.order_executor import OrderExecutor

class ServiceRegistry:
    """
    Registry of core services available to plugins.
    Plugins receive this via their on_start method.
    """
    def __init__(
        self,
        exchange_client: BinanceFuturesClient = None,
        notification_manager: NotificationManager = None,
        risk_manager: RiskManager = None,
        position_manager: PositionManager = None,
        order_executor: OrderExecutor = None,
    ):
        self.exchange = exchange_client
        self.notifications = notification_manager
        self.risk = risk_manager
        self.positions = position_manager
        self.executor = order_executor