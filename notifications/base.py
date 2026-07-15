from abc import ABC, abstractmethod
from models.notification import NotificationMessage

class BaseNotifier(ABC):
    @abstractmethod
    async def send(self, message: NotificationMessage) -> bool:
        """Return True if sent successfully."""
        ...