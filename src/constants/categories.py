"""
Defines content categories for feed item classification.
"""

from typing import Final

CATEGORY_MOVIE: Final[str] = "Movie"
CATEGORY_TV: Final[str] = "TV Series"
CATEGORY_STREAMING: Final[str] = "Streaming"
CATEGORY_BOX_OFFICE: Final[str] = "Box Office"
CATEGORY_AWARDS: Final[str] = "Awards"
CATEGORY_INDUSTRY: Final[str] = "Industry News"

ALL_CATEGORIES: Final[list[str]] = [
    CATEGORY_MOVIE,
    CATEGORY_TV,
    CATEGORY_STREAMING,
    CATEGORY_BOX_OFFICE,
    CATEGORY_AWARDS,
    CATEGORY_INDUSTRY,
]
