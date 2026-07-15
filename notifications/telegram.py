import aiohttp
from models.notification import NotificationMessage
from notifications.base import BaseNotifier
from utils.logger import setup_logger

logger = setup_logger(__name__)

class TelegramNotifier(BaseNotifier):
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    async def send(self, message: NotificationMessage) -> bool:
        text = f"*{message.title}*\n{message.body}"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_url, json=payload) as resp:
                    if resp.status == 200:
                        logger.debug("Telegram message sent")
                        return True
                    else:
                        logger.error(f"Telegram send failed: {resp.status}")
                        return False
        except Exception as e:
            logger.error(f"Telegram error: {e}")
            return False