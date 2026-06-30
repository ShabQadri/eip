"""
Feed Registry utility for reading configured RSS sources from JSON.
"""

import json
from pathlib import Path
from typing import List, Dict, Any

class FeedRegistry:
    """
    Manages loading and parsing of sources from data/feeds/feed_sources.json.
    """
    def __init__(self) -> None:
        project_root = Path(__file__).resolve().parent.parent.parent
        self.sources_path = project_root / "data" / "feeds" / "feed_sources.json"

    def load_configured_sources(self) -> List[Dict[str, Any]]:
        """Loads and returns source config items."""
        if not self.sources_path.exists():
            return []
        
        with open(self.sources_path, "r", encoding="utf-8") as f:
            return json.load(f)
