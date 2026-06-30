"""
Unit tests for the SimilarityEngine.
"""

import tempfile
import os
import json
from pathlib import Path
from src.processing.events.alias_manager import AliasManager
from src.processing.events.similarity_engine import SimilarityEngine

def test_similarity_engine_calculations() -> None:
    # 1. Setup temporary configurations
    aliases_rules = {
        "Dune Messiah": ["dune 3", "dune part three"]
    }
    patterns_rules = {
        "PRODUCTION_START": ["begins filming", "starts production", "cameras roll"]
    }

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8") as tmp_a:
        json.dump(aliases_rules, tmp_a)
        tmp_a_path = Path(tmp_a.name)

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8") as tmp_p:
        json.dump(patterns_rules, tmp_p)
        tmp_p_path = Path(tmp_p.name)

    try:
        alias_manager = AliasManager(rules_path=tmp_a_path)
        similarity_engine = SimilarityEngine(alias_manager, patterns_path=tmp_p_path)

        # Exact match (after cleanup)
        s_exact = similarity_engine.calculate_similarity(
            "Dune: Messiah", "Dune Messiah"
        )
        assert s_exact == 100.0

        # Alias match
        s_alias = similarity_engine.calculate_similarity(
            "Dune 3", "Dune Messiah"
        )
        assert s_alias == 100.0

        # Pattern detection
        assert similarity_engine.detect_pattern("Dune Messiah Begins Filming") == "PRODUCTION_START"
        assert similarity_engine.detect_pattern("Some random movie review") is None

        # Core title extraction
        assert similarity_engine.extract_core_title("Dune Messiah Begins Filming") == "dune messiah"
        assert similarity_engine.extract_core_title("Dune 3 Starts Production") == "dune 3"

        # Fuzzy matching with bonus
        # "Dune Messiah Begins Filming" vs "Dune Messiah Starts Production"
        # Since they are same franchise ("Dune") and same pattern ("PRODUCTION_START"), we get a bonus
        s_bonus = similarity_engine.calculate_similarity(
            title1="Dune Messiah Begins Filming",
            title2="Dune Messiah Starts Production",
            franchise1="Dune",
            franchise2="Dune"
        )
        # Without pattern suffix, core title is "dune messiah" for both, resolving to exact match (100)
        assert s_bonus == 100.0

    finally:
        os.remove(tmp_a_path)
        os.remove(tmp_p_path)
