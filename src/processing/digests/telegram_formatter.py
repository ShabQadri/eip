import logging
from typing import List, Optional
from urllib.parse import urlparse
from src.models.event import Event

logger = logging.getLogger("eip.telegram_formatter")

class TelegramFormatter:
    """
    Formats events and digests into Telegram-friendly text blocks using MarkdownV2.
    """
    def __init__(self) -> None:
        pass

    def escape_markdown_v2(self, text: str) -> str:
        """
        Escapes Telegram MarkdownV2 special characters.
        """
        if not text:
            return ""
        escape_chars = r"\_*[]()~`>#+-=|{}.!"
        escaped = []
        for char in text:
            if char in escape_chars:
                escaped.append("\\" + char)
            else:
                escaped.append(char)
        return "".join(escaped)

    def escape_link_url(self, url: str) -> str:
        """
        Escapes only ')' and '\\' inside inline link URLs.
        """
        if not url:
            return ""
        return url.replace("\\", "\\\\").replace(")", "\\)")

    def format_event_for_telegram(self, title: str, story_text: str, source_urls: List[str], trailer_url: Optional[str] = None) -> str:
        """
        Compiles headline, body story, sources list, and trailer link into a compliant MarkdownV2 post.
        """
        escaped_title = self.escape_markdown_v2(title.strip())
        
        # Split body into paragraphs, escape each, and join with double newlines
        paragraphs = [self.escape_markdown_v2(p.strip()) for p in story_text.split("\n\n") if p.strip()]
        
        body_content = "\n\n".join(paragraphs)
        
        # Check if the generated story already contains the headline emoji prefix
        if body_content.startswith("🎬") or body_content.startswith("\\🎬"):
            # Format the first paragraph as a bold headline
            lines = body_content.split("\n\n")
            if lines:
                first_line = lines[0]
                clean_first = first_line.replace("🎬", "").replace("\\🎬", "").strip()
                lines[0] = f"🎬 *{clean_first}*"
                message = "\n\n".join(lines)
            else:
                message = body_content
        else:
            message = f"🎬 *{escaped_title}*\n\n{body_content}"

        # Append source links (using canonical source URLs)
        if source_urls:
            valid_sources = [url for url in source_urls if url]
            if len(valid_sources) == 1:
                escaped_url = self.escape_link_url(valid_sources[0])
                message += f"\n\n🔗 [Source]({escaped_url})"
            elif len(valid_sources) > 1:
                links = []
                for url in valid_sources[:3]:
                    parsed = urlparse(url)
                    domain = parsed.netloc or "Source"
                    if domain.startswith("www."):
                        domain = domain[4:]
                    escaped_domain = self.escape_markdown_v2(domain)
                    escaped_url = self.escape_link_url(url)
                    links.append(f"• [{escaped_domain}]({escaped_url})")
                message += f"\n\n🔗 Sources:\n" + "\n".join(links)

        # Append trailer link if available
        if trailer_url:
            escaped_trailer = self.escape_link_url(trailer_url)
            message += f"\n\n▶️ [Watch Trailer]({escaped_trailer})"

        return message

    def format_breaking_alert(self, event: Event) -> str:
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
        return self.format_breaking_alert(event)

    def format_digest_post(self, events: List[Event]) -> str:
        from src.processing.digests.digest_formatter import DigestFormatter
        formatter = DigestFormatter()
        plain_text = formatter.format_digest(events)
        return self.format_digest_message(plain_text)
