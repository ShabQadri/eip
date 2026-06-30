"""
Telegram package for handling bot interactions and sending digests.
"""

from src.models import Digest

class TelegramPublisher:
    """
    Communicates with the Telegram Bot API to post structured digests.
    """
    def __init__(self, bot_token: str, channel_id: str) -> None:
        self.bot_token = bot_token
        self.channel_id = channel_id

    async def publish_digest_to_channel(self, digest: Digest) -> bool:
        """
        Sends the compiled digest text to the configured channel.
        """
        # Telegram Bot HTTP client request goes here
        return True
