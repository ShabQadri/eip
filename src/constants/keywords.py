"""
Keywords used for initial filtering, category classification, and keyword-based sorting.
"""

from typing import Final

# Topic classifications
KEYWORD_MOVIES: Final[list[str]] = [
    "movie", "film", "cinema", "box office", "theatrical", "director", "actor"
]

KEYWORD_TV: Final[list[str]] = [
    "series", "episode", "showrunner", "sitcom", "drama", "telecast", "television"
]

KEYWORD_STREAMING: Final[list[str]] = [
    "netflix", "disney+", "hbo max", "max", "hulu", "prime video", "apple tv+"
]

# Importance classifications
KEYWORD_BREAKING: Final[list[str]] = [
    "breaking", "urgent", "just in", "revealed", "announced"
]

KEYWORD_EXCLUSIVE: Final[list[str]] = [
    "exclusive", "scoop", "first look"
]
