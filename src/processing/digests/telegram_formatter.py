import logging
from typing import List
from src.models.event import Event

logger = logging.getLogger("eip.telegram_formatter")


class TelegramFormatter:
    """
    Formats events and digests into Telegram-friendly text blocks.
    """
    def __init__(self) -> None:
        pass

    def escape_markdown_v2(self, text: str) -> str:
        """
        Escapes Telegram MarkdownV2 special characters.
        """
        if not text:
            return ""
        # Characters to escape in Telegram MarkdownV2:
        # \ _ * [ ] ( ) ~ ` > # + - = | { } . !
        escape_chars = r"\__*[]()~`>#+-=|{}.!"
        escaped = []
        for char in text:
            if char in escape_chars:
                escaped.append("\\" + char)
            else:
                escaped.append(char)
        return "".join(escaped)

    def format_breaking_alert(self, event: Event) -> str:
        """
        Formats a breaking event into a Telegram breaking alert post.
        """
        display_title = getattr(event, "display_title", None) or getattr(event, "canonical_title", "Unknown")
        importance = getattr(event, "importance_score", None)
        if importance is None:
            importance = "N/A"
        source_count = getattr(event, "source_count", None)
        if source_count is None:
            source_count = 1

        lines = [
            "🚨 BREAKING",
            "",
            f"🎬 {display_title}",
            "",
            f"Importance: {importance}",
            f"Sources: {source_count}",
            "",
            "#Entertainment #Breaking"
        ]
        raw_msg = "\n".join(lines)
        return self.escape_markdown_v2(raw_msg)

    def format_digest_message(self, digest_text: str) -> str:
        """
        Converts plain text digest into a Telegram-safe MarkdownV2 string.
        """
        return self.escape_markdown_v2(digest_text)

    def format_breaking_post(self, event: Event) -> str:
        """
        Formats a breaking event into a Telegram breaking alert post (skeleton backward compatibility).
        """
        return self.format_breaking_alert(event)

    def format_digest_post(self, events: List[Event]) -> str:
        """
        Formats a list of events into a Telegram digest post (skeleton backward compatibility).
        """
        from src.processing.digests.digest_formatter import DigestFormatter
        formatter = DigestFormatter()
        plain_text = formatter.format_digest(events)
        return self.format_digest_message(plain_text)

