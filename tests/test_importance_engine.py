"""
Unit tests for ImportanceEngine scoring weights and category classifications.
"""

from src.feeds.importance_engine import ImportanceEngine
from src.models.article import Article

def test_importance_engine_scoring() -> None:
    """Verifies that importance scoring matches configured keyword weights."""
    engine = ImportanceEngine()

    # Trailer news should score highly
    trailer_art = Article(
        source_id="dummy",
        title="Official Trailer for new Star Wars show released",
        url="https://starwars.com/trailer",
        hash="hash1",
        description="Check out the brand new teaser."
    )
    engine.score_article(trailer_art)
    assert trailer_art.importance_score == 95
    assert trailer_art.category == "Movie"

    # Renewed TV series
    tv_art = Article(
        source_id="dummy",
        title="Squid Game renewed for Season 3",
        url="https://netflix.com/squid-game-renewed",
        hash="hash2",
        description="Netflix confirmed the greenlit season."
    )
    engine.score_article(tv_art)
    assert tv_art.importance_score == 90
    assert tv_art.category == "TV Series"

    # Box office news
    bo_art = Article(
        source_id="dummy",
        title="Dune Part Two hits box office milestone",
        url="https://variety.com/dune-bo",
        hash="hash3",
        description="The theatrical release reached a new record."
    )
    engine.score_article(bo_art)
    assert bo_art.importance_score == 70
    assert bo_art.category == "Movie"

    # Generic low value item
    generic_art = Article(
        source_id="dummy",
        title="Industry reports revenue growth",
        url="https://variety.com/interview",
        hash="hash4",
        description="General earnings report show growth in multiple sectors."
    )
    engine.score_article(generic_art)
    assert generic_art.importance_score == 10
    assert generic_art.category == "Industry News"
