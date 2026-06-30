"""
Digest compilation package.
Implements rule-based digest formatting and is decoupled from LLM/Gemini dependencies.
Designed to be extensible for downstream AI polishing/enhancements.
"""

from datetime import datetime
from src.models import Article, Digest

class RuleBasedDigestCompiler:
    """
    Compiles feed items into formatted markdown text digests via structural rules.
    Runs completely offline without external LLM dependencies.
    """
    def __init__(self) -> None:
        pass

    def compile(self, items: list[Article]) -> Digest:
        """
        Aggregates, categories, and formats feed items into a structured Telegram message.
        """
        lines = [
            f"🎬 *Entertainment Digest* - {datetime.now().strftime('%d %B %Y')}",
            "========================================\n"
        ]

        # Simple rule-based formatting template
        for item in items:
            category_label = f"[{item.category.upper()}] " if item.category else ""
            lines.append(f"• {category_label}*{item.title}*")
            lines.append(f"  {item.description[:150]}...")
            lines.append(f"  🔗 [Source]({item.url})\n")

        digest_text = "\n".join(lines)

        return Digest(
            compiled_at=datetime.now(),
            content=digest_text
        )
