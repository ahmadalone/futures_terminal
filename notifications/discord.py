import aiohttp
from models.notification import NotificationMessage
from notifications.base import BaseNotifier
from utils.logger import setup_logger

logger = setup_logger(__name__)

class DiscordNotifier(BaseNotifier):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send(self, message: NotificationMessage) -> bool:
        embed = {
            "title": message.title,
            "description": message.body,
            "color": 0x00ff00 if message.level == "info" else 0xffa500 if message.level == "warning" else 0xff0000,
            "timestamp": message.timestamp.isoformat()
        }
        payload = {"embeds": [embed]}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload) as resp:
                    if resp.status == 204:
                        logger.debug("Discord message sent")
                        return True
                    else:
                        logger.error(f"Discord send failed: {resp.status}")
                        return False
        except Exception as e:
            logger.error(f"Discord error: {e}")
            return False