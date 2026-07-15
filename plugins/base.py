"""
PluginBase – every plugin must inherit from this class.
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from models.signal import Signal
from plugins.services import ServiceRegistry
from utils.logger import setup_logger

logger = setup_logger(__name__)

class PluginBase(ABC):
    """
    Base class for all trading plugins.
    Plugins must implement on_tick and can optionally override on_start/on_stop.
    """
    def __init__(self, manifest, services: ServiceRegistry):
        self.manifest = manifest
        self.services = services
        self.logger = logger.getChild(manifest.name)
        self._enabled = True

    @abstractmethod
    async def on_tick(self, market_data: dict) -> List[Signal]:
        """
        Called at each tick (candle close). Must return a list of signals.
        market_data is a dict symbol -> latest OHLCV or ticker info.
        """
        ...

    async def on_start(self):
        """Called when the plugin is loaded and started."""
        self.logger.info(f"Plugin {self.manifest.name} started")

    async def on_stop(self):
        """Called when the plugin is stopped or unloaded."""
        self.logger.info(f"Plugin {self.manifest.name} stopped")

    def enable(self):
        self._enabled = True

    def disable(self):
        self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled