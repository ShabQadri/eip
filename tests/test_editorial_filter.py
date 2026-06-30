"""
Unit tests for EditorialFilter and RSSParser pre-filtering logic.
"""

from src.feeds.rss_parser import RSSParser
from src.feeds.editorial_filter import EditorialFilter
from src.models.article import Article

def test_rss_parser_pre_filtering() -> None:
    """Verifies that the RSSParser identifies and pre-filters obvious blacklist terms."""
    blacklist = ["dating", "airport", "paparazzi", "net worth"]
    parser = RSSParser(blacklist_keywords=blacklist)

    # Obvious gossip item
    gossip_item = {
        "title": "Actor spotted at airport with new partner",
        "summary": "Rumors of dating circulate.",
        "description": ""
    }
    assert parser.pre_filter_entry(gossip_item) is True

    # High-value news item
    clean_item = {
        "title": "Director confirmed for upcoming Dune sequel",
        "summary": "Official announcement expected at festival.",
        "description": ""
    }
    assert parser.pre_filter_entry(clean_item) is False

def test_editorial_filter_evaluation() -> None:
    """Verifies that the EditorialFilter rejects gossip and labels reasons correctly."""
    editorial_filter = EditorialFilter()

    # Gossip article
    gossip_art = Article(
        source_id="dummy",
        title="Pop star spotted kissing partner",
        url="https://variety.com/gossip-news",
        hash="hash1",
        description="Exclusive photos from their private vacation."
    )
    approved, reason = editorial_filter.evaluate_article(gossip_art)
    assert approved is False
    assert reason == "GOSSIP"

    # Clickbait article
    clickbait_art = Article(
        source_id="dummy",
        title="Check out their weight loss transformation!",
        url="https://variety.com/transformation",
        hash="hash2",
        description="Fans furious over throwback childhood photo."
    )
    approved, reason = editorial_filter.evaluate_article(clickbait_art)
    assert approved is False
    assert reason == "CLICKBAIT"

    # Valid news article
    valid_art = Article(
        source_id="dummy",
        title="Marvel confirms official trailer date for Avengers",
        url="https://variety.com/avengers-trailer",
        hash="hash3",
        description="Official trailer will premiere next week."
    )
    approved, reason = editorial_filter.evaluate_article(valid_art)
    assert approved is True
    assert reason is None
