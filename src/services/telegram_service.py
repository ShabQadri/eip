import asyncio
import aiohttp
import logging
import concurrent.futures
from typing import Optional, Dict, Any

logger = logging.getLogger("eip.telegram_service")

class TelegramService:
    """
    Service to publish digest messages and breaking alerts to Telegram channels.
    """
    def __init__(self, bot_token: Optional[str] = None, channel_id: Optional[str] = None) -> None:
        from src.config.settings import settings
        self.bot_token = bot_token or settings.TELEGRAM_BOT_TOKEN
        self.channel_id = channel_id or settings.TELEGRAM_CHANNEL_ID

    async def _send_message_async(self, text: str) -> dict:
        if not self.bot_token or not self.channel_id:
            logger.error("Telegram bot token or channel ID not configured.")
            return {
                "success": False,
                "message_id": None,
                "error": "Configuration error: Missing bot token or channel ID"
            }

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.channel_id,
            "text": text,
            "parse_mode": "MarkdownV2"
        }

        # Timeout: 15 seconds
        timeout = aiohttp.ClientTimeout(total=15.0)

        # Retry config: 3 attempts, exponential backoff: 1s, 2s, 4s
        attempts = 3
        backoff = 1.0
        last_error = None

        async with aiohttp.ClientSession(timeout=timeout) as session:
            for attempt in range(1, attempts + 1):
                try:
                    async with session.post(url, json=payload) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get("ok"):
                                message_id = data.get("result", {}).get("message_id")
                                return {
                                    "success": True,
                                    "message_id": message_id,
                                    "error": None
                                }
                            else:
                                err_desc = data.get("description", "Unknown API error")
                                logger.error(f"Telegram API error (attempt {attempt}): {err_desc}")
                                return {
                                    "success": False,
                                    "message_id": None,
                                    "error": f"API error: {err_desc}"
                                }
                        else:
                            text_resp = await response.text()
                            logger.error(f"Telegram HTTP status {response.status} (attempt {attempt}): {text_resp}")
                            last_error = f"HTTP {response.status}: {text_resp}"
                except aiohttp.ClientError as e:
                    logger.error(f"Telegram client error (attempt {attempt}): {e}")
                    last_error = str(e)
                except asyncio.TimeoutError:
                    logger.error(f"Telegram timeout error (attempt {attempt})")
                    last_error = "Timeout error"
                except Exception as e:
                    logger.error(f"Telegram unexpected error (attempt {attempt}): {e}")
                    last_error = str(e)

                # Backoff before retry (if not the last attempt)
                if attempt < attempts:
                    await asyncio.sleep(backoff)
                    backoff *= 2.0

            return {
                "success": False,
                "message_id": None,
                "error": f"Failed after {attempts} attempts. Last error: {last_error}"
            }

    def send_message(self, text: str) -> dict:
        """
        Publishes a message to Telegram channel.
        """
        res = None
        try:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            if loop.is_running():
                # Run the coroutine in another thread with a new event loop
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self._send_message_async(text))
                    res = future.result()
            else:
                res = loop.run_until_complete(self._send_message_async(text))
        except Exception as e:
            logger.error(f"TelegramService sync wrapper error: {e}")
            res = {
                "success": False,
                "message_id": None,
                "error": f"Internal wrapper error: {e}"
            }

        # Record failure metric if not success
        if res and not res.get("success"):
            try:
                from src.database.database import SessionLocal
                from src.services.metrics_service import MetricsService
                db = SessionLocal()
                try:
                    MetricsService().increment(db, "telegram_failures")
                    db.commit()
                except Exception as db_err:
                    logger.error(f"DB error recording telegram_failures: {db_err}")
                finally:
                    db.close()
            except Exception as e:
                logger.error(f"Failed to record telegram_failures metric: {e}")

        return res

    def send_digest(self, digest_text: str) -> dict:
        """
        Sends digest message to Telegram.
        """
        return self.send_message(digest_text)

    def send_breaking_alert(self, alert_text: str) -> dict:
        """
        Sends breaking alert message to Telegram.
        """
        return self.send_message(alert_text)
