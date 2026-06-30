"""
Regex patterns for parsing, filtering, and sanitizing raw feed content.
"""

import re
from typing import Final

# Pattern to match HTML tags for text sanitization
HTML_TAG_CLEANSER: Final[re.Pattern[str]] = re.compile(r"<[^>]*>")

# Pattern to detect release years (e.g. (2026) or [2026])
YEAR_DETECTOR: Final[re.Pattern[str]] = re.compile(r"\b(19|20)\d{2}\b")

# Pattern to capture TV Season references (e.g., Season 2, S02, Season II)
TV_SEASON_DETECTOR: Final[re.Pattern[str]] = re.compile(
    r"\b(?:season\s+\d+|s\d{1,2})\b", 
    re.IGNORECASE
)
