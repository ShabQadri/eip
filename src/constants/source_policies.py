"""
Policies defining ingestion behaviors for different media outlets and RSS feeds.
"""

from typing import Final, TypedDict

class SourcePolicy(TypedDict):
    name: str
    trust_weight: float
    refresh_interval_minutes: int
    auto_publish: bool

# Default fallback policy for unidentified sources
DEFAULT_POLICY: Final[SourcePolicy] = {
    "name": "Default",
    "trust_weight": 1.0,
    "refresh_interval_minutes": 60,
    "auto_publish": False,
}

# Source-specific rules
TRUSTED_SOURCE_POLICIES: Final[dict[str, SourcePolicy]] = {
    "variety": {
        "name": "Variety",
        "trust_weight": 1.5,
        "refresh_interval_minutes": 30,
        "auto_publish": True,
    },
    "hollywood_reporter": {
        "name": "The Hollywood Reporter",
        "trust_weight": 1.5,
        "refresh_interval_minutes": 30,
        "auto_publish": True,
    },
    "deadline": {
        "name": "Deadline",
        "trust_weight": 1.4,
        "refresh_interval_minutes": 30,
        "auto_publish": True,
    },
}
