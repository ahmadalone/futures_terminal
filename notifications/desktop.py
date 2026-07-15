import asyncio
from notifications.base import BaseNotifier
from models.notification import NotificationMessage
from utils.logger import setup_logger

logger = setup_logger(__name__)

class DesktopNotifier(BaseNotifier):
    def __init__(self):
        try:
            import plyer
            self.notification = plyer.notification
        except ImportError:
            self.notification = None

    async def send(self, message: NotificationMessage) -> bool:
        if not self.notification:
            return False
        try:
            await asyncio.to_thread(
                self.notification.notify,
                title=message.title,
                message=message.body,
                timeout=5
            )
            return True
        except Exception as e:
            logger.error(f"Desktop notification error: {e}")
            return False