"""
Franchise detection service based on keyword mappings.
"""

import json
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

class FranchiseDetector:
    """
    Detects entertainment franchises and assigns region categories based on keywords.
    """
    def __init__(self, rules_path: Optional[Path] = None) -> None:
        if rules_path is None:
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            rules_path = project_root / "data" / "events" / "franchise_rules.json"

        self.rules: Dict[str, Any] = {}
        if rules_path.exists():
            with open(rules_path, "r", encoding="utf-8") as f:
                self.rules = json.load(f)

    def detect(self, title: str, description: str = "") -> Tuple[Optional[str], Optional[str]]:
        """
        Scans title and description for franchise keyword matches.
        Returns a tuple of (franchise_name, region) or (None, None) if not found.
        """
        text = f"{title or ''} {description or ''}".lower()

        for franchise_name, config in self.rules.items():
            keywords = config.get("keywords", [])
            region = config.get("region")
            
            for kw in keywords:
                if kw.lower() in text:
                    return franchise_name, region

        return None, None
