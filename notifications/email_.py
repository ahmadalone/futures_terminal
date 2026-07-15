import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from models.notification import NotificationMessage
from notifications.base import BaseNotifier
from utils.logger import setup_logger

logger = setup_logger(__name__)

class EmailNotifier(BaseNotifier):
    def __init__(self, smtp_host: str, smtp_port: int, username: str, password: str, recipient: str):
        self.host = smtp_host
        self.port = smtp_port
        self.username = username
        self.password = password
        self.recipient = recipient

    async def send(self, message: NotificationMessage) -> bool:
        try:
            return await asyncio.to_thread(self._send_sync, message)
        except Exception as e:
            logger.error(f"Email error: {e}")
            return False

    def _send_sync(self, message: NotificationMessage) -> bool:
        msg = MIMEMultipart()
        msg['From'] = self.username
        msg['To'] = self.recipient
        msg['Subject'] = message.title
        msg.attach(MIMEText(message.body, 'plain'))
        with smtplib.SMTP(self.host, self.port) as server:
            server.starttls()
            server.login(self.username, self.password)
            server.sendmail(self.username, self.recipient, msg.as_string())
        return True