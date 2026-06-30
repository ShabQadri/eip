"""
Editorial filter evaluating articles against blacklisted entertainment content.
"""

import json
from typing import Optional, Tuple, Dict, List
from pathlib import Path
from src.models.article import Article

class EditorialFilter:
    """
    Rejects gossip, rumors, clickbait, and personal life stories, assigning a specific filter reason.
    """
    def __init__(self) -> None:
        project_root = Path(__file__).resolve().parent.parent.parent
        rules_path = project_root / "data" / "feeds" / "editorial_rules.json"

        with open(rules_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.blacklist_keywords = data.get("blacklist_keywords", [])
        self.filter_reasons: Dict[str, List[str]] = data.get("filter_reasons", {})

        # Create mapping of lowercase keyword to reason category
        self.keyword_to_reason: Dict[str, str] = {}
        for reason, keywords in self.filter_reasons.items():
            for kw in keywords:
                self.keyword_to_reason[kw.lower()] = reason

    def evaluate_article(self, article: Article) -> Tuple[bool, Optional[str]]:
        """
        Evaluates the title and description of the article against blacklist rules.
        Returns:
            Tuple[is_approved, filter_reason_string_or_none]
        """
        title = (article.title or "").lower()
        description = (article.description or "").lower()

        for kw in self.blacklist_keywords:
            kw_lower = kw.lower()
            if kw_lower in title or kw_lower in description:
                # Default to LOW_VALUE if not explicitly mapped
                reason = self.keyword_to_reason.get(kw_lower, "LOW_VALUE")
                return False, reason

        return True, None
