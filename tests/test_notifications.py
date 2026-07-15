import pytest
from models.notification import NotificationMessage
from notifications.manager import NotificationManager
from notifications.base import BaseNotifier
from unittest.mock import AsyncMock

class DummyNotifier(BaseNotifier):
    def __init__(self):
        self.sent = []
    async def send(self, msg):
        self.sent.append(msg)
        return True

@pytest.mark.asyncio
async def test_notification_manager():
    nm = NotificationManager()
    notifier = DummyNotifier()
    nm.add_notifier(notifier)
    msg = NotificationMessage(title="Test", body="Hello")
    await nm.notify(msg)
    # Wait a bit for asyncio.ensure_future
    import asyncio
    await asyncio.sleep(0.1)
    assert len(notifier.sent) == 1
    assert notifier.sent[0].title == "Test"