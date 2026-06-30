"""
Unit and integration tests for the EventMatcher.
"""

import tempfile
import os
import json
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.base import Base
from src.models.event import Event
from src.models.article import Article
from src.processing.events.alias_manager import AliasManager
from src.processing.events.franchise_detector import FranchiseDetector
from src.processing.events.similarity_engine import SimilarityEngine
from src.processing.events.event_matcher import EventMatcher

def test_event_matcher_flow() -> None:
    # 1. Setup DB
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # 2. Setup mock rules
    aliases_rules = {"Dune Messiah": ["dune 3"]}
    franchises_rules = {"Dune": {"keywords": ["dune"], "region": "HOLLYWOOD"}}

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8") as tmp_a:
        json.dump(aliases_rules, tmp_a)
        tmp_a_path = Path(tmp_a.name)

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8") as tmp_f:
        json.dump(franchises_rules, tmp_f)
        tmp_f_path = Path(tmp_f.name)

    try:
        alias_manager = AliasManager(rules_path=tmp_a_path)
        franchise_detector = FranchiseDetector(rules_path=tmp_f_path)
        similarity_engine = SimilarityEngine(alias_manager)
        matcher = EventMatcher(similarity_engine, franchise_detector)

        # Populate database with an event
        event = Event(
            canonical_title="Dune Messiah",
            event_type="Movie",
            importance_score=75,
            status="ANNOUNCED",
            aliases_json=["dune 3"]
        )
        db.add(event)
        db.commit()

        # 3. Test Match Cases
        # Case A: Matches exact title (resolves via core title)
        art_exact = Article(
            source_id="variety",
            title="Dune Messiah Begins Filming",
            hash="h1",
            url="url1"
        )
        match_a = matcher.find_match(db, art_exact)
        assert match_a is not None
        assert match_a.id == event.id

        # Case B: Matches via alias
        art_alias = Article(
            source_id="deadline",
            title="Dune 3 Starts Production",
            hash="h2",
            url="url2"
        )
        match_b = matcher.find_match(db, art_alias)
        assert match_b is not None
        assert match_b.id == event.id

        # Case C: No match (completely different movie)
        art_other = Article(
            source_id="collider",
            title="Spiderman 4 greenlit",
            hash="h3",
            url="url3"
        )
        match_c = matcher.find_match(db, art_other)
        assert match_c is None

    finally:
        db.close()
        os.remove(tmp_a_path)
        os.remove(tmp_f_path)
