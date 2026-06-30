"""
Emoji representations for categorized stories and events inside Telegram posts.
"""

from typing import Final
from src.constants.categories import (
    CATEGORY_MOVIE,
    CATEGORY_TV,
    CATEGORY_STREAMING,
    CATEGORY_BOX_OFFICE,
    CATEGORY_AWARDS,
    CATEGORY_INDUSTRY,
)

# Map categories to visual badges
CATEGORY_EMOJIS: Final[dict[str, str]] = {
    CATEGORY_MOVIE: "🎬",
    CATEGORY_TV: "📺",
    CATEGORY_STREAMING: "🍿",
    CATEGORY_BOX_OFFICE: "💰",
    CATEGORY_AWARDS: "🏆",
    CATEGORY_INDUSTRY: "📰",
}

# Editorial visual tags
EDITORIAL_EMOJIS: Final[dict[str, str]] = {
    "breaking": "🚨",
    "exclusive": "✨",
    "trailer": "▶️",
    "rumor": "👀",
    "review": "⭐️",
    "announcement": "📢",
}
