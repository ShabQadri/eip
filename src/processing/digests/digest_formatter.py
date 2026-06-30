import logging
from datetime import datetime, timezone
from typing import List, Optional
from src.models.event import Event

logger = logging.getLogger("eip.digest_formatter")


class DigestFormatter:
    """
    Formats selected events into human-readable digests.
    """
    def __init__(self, current_date_override: Optional[str] = None) -> None:
        self.current_date_override = current_date_override

    def format_digest(
        self,
        events: List[Event],
        digest_type: str = "morning"
    ) -> str:
        """
        Formats selected canonical events into premium twice-daily digest text.
        """
        if self.current_date_override:
            current_date = self.current_date_override
        else:
            current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        lines = []
        lines.append("🎬 Entertainment Intelligence Digest")
        lines.append(f"🗓 {current_date}")

        if not events:
            lines.append("")
            lines.append("No major entertainment developments at this time.")
            return "\n".join(lines)

        for idx, event in enumerate(events[:12], 1):
            display_title = getattr(event, "display_title", None) or getattr(event, "canonical_title", "Unknown")
            
            importance = getattr(event, "importance_score", None)
            if importance is None:
                importance = "N/A"
                
            source_count = getattr(event, "source_count", None)
            if source_count is None:
                source_count = 1
                
            pattern = getattr(event, "event_pattern", None)
            if pattern is None:
                pattern = "Unknown"

            lines.append("")
            lines.append(f"{idx}. {display_title}")
            lines.append(f"   • Importance: {importance}")
            lines.append(f"   • Sources: {source_count}")
            lines.append(f"   • Pattern: {pattern}")

        return "\n".join(lines)

