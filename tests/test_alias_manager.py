"""
Unit tests for the AliasManager class.
"""

import tempfile
import os
import json
from pathlib import Path
from src.processing.events.alias_manager import AliasManager

def test_alias_manager_lookups() -> None:
    # Build a temporary rules config file
    rules = {
        "Dune Messiah": [
            "dune 3",
            "dune: messiah",
            "dune part three"
        ],
        "SSMB29": [
            "mahesh babu 29",
            "ssmb 29"
        ]
    }
    
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8") as tmp:
        json.dump(rules, tmp)
        tmp_path = Path(tmp.name)

    try:
        manager = AliasManager(rules_path=tmp_path)
        
        # Test canonical resolutions (casing preserved)
        assert manager.get_canonical_title("dune 3") == "Dune Messiah"
        assert manager.get_canonical_title("DUNE: MESSIAH") == "Dune Messiah"
        assert manager.get_canonical_title("Dune Messiah") == "Dune Messiah"
        assert manager.get_canonical_title("ssmb 29") == "SSMB29"
        assert manager.get_canonical_title("mahesh babu 29") == "SSMB29"
        
        # Unmapped
        assert manager.get_canonical_title("unknown movie") is None

        # Test fetching aliases
        aliases = manager.get_aliases("Dune Messiah")
        assert "dune 3" in aliases
        assert "dune messiah" in aliases
        assert "dune part 3" in aliases  # due to title_cleaner resolving part three -> part 3

    finally:
        os.remove(tmp_path)
