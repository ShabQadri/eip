"""
Importance scoring engine using keyword weight configurations.
"""

import json
from typing import Dict, Any
from pathlib import Path
from src.models.article import Article

class ImportanceEngine:
    """
    Evaluates articles to assign importance scores and content categories.
    """
    def __init__(self) -> None:
        project_root = Path(__file__).resolve().parent.parent.parent
        rules_path = project_root / "data" / "feeds" / "editorial_rules.json"

        with open(rules_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Mapping of positive keyword string to integer score
        self.positive_keywords: Dict[str, int] = data.get("positive_keywords", {})

    def score_article(self, article: Article) -> None:
        """
        Determines the importance score and category mapping of an article.
        Modifies properties on the Article instance in-place.
        """
        title = (article.title or "").lower()
        description = (article.description or "").lower()

        max_score = 10  # Fallback importance score for generic items
        matched_kw = ""

        # Score based on positive keyword hits
        for kw, score in self.positive_keywords.items():
            kw_lower = kw.lower()
            if kw_lower in title or kw_lower in description:
                if score > max_score:
                    max_score = score
                    matched_kw = kw_lower

        article.importance_score = max_score

        # Category Heuristic Classification
        category = "Industry News"  # Fallback category
        
        tv_indicators = ["season", "episode", "showrunner", "cancelled", "renewed", "sitcom"]
        streaming_indicators = ["streaming", "netflix", "prime", "hulu", "disney", "ott"]
        movie_indicators = ["movie", "film", "box office", "theatrical", "cinema"]

        if any(t in title or t in description for t in tv_indicators) or matched_kw in ["season", "greenlit", "renewed", "cancellation", "cancelled"]:
            category = "TV Series"
        elif any(s in title or s in description for s in streaming_indicators) or matched_kw in ["streaming date", "ott release"]:
            category = "Streaming"
        elif any(m in title or m in description for m in movie_indicators) or matched_kw in ["official trailer", "trailer", "box office milestone", "box office"]:
            category = "Movie"

        article.category = category
