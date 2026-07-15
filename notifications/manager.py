"""
NotificationManager – holds notifiers and dispatches messages based on event types.
"""
from typing import List
from models.notification import NotificationMessage
from notifications.base import BaseNotifier
from utils.logger import setup_logger

logger = setup_logger(__name__)

class NotificationManager:
    def __init__(self):
        self.notifiers: List[BaseNotifier] = []

    def add_notifier(self, notifier: BaseNotifier):
        self.notifiers.append(notifier)

    async def notify(self, message: NotificationMessage):
        for notifier in self.notifiers:
            asyncio.ensure_future(self._send_and_log(notifier, message))

    async def _send_and_log(self, notifier: BaseNotifier, message: NotificationMessage):
        try:
            success = await notifier.send(message)
            if not success:
                logger.warning(f"Notification via {type(notifier).__name__} failed")
        except Exception as e:
            logger.error(f"Unhandled notifier error: {e}")