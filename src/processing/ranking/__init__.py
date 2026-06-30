"""
Ranking subpackage for calculating story importance scores and sorting digests.
"""

from src.models import FeedItem

class StoryRanker:
    """
    Evaluates feed items based on source authority, keywords, and publication freshness.
    """
    def __init__(self) -> None:
        pass

    def compute_importance_score(self, item: FeedItem) -> float:
        """
        Calculates a numerical importance score for a given FeedItem.
        """
        # Score calculation goes here
        return 1.0

    def rank(self, items: list[FeedItem]) -> list[FeedItem]:
        """
        Sorts feed items in descending order of calculated importance score.
        """
        return sorted(
            items, 
            key=self.compute_importance_score, 
            reverse=True
        )
