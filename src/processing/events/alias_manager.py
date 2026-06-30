"""
Alias manager mapping titles to canonical strings.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from src.processing.events.title_cleaner import TitleCleaner

class AliasManager:
    """
    Manages canonical titles and their aliases loaded from JSON.
    All lookup keys and aliases are cleaned internally to ensure match robustness.
    """
    def __init__(self, rules_path: Optional[Path] = None) -> None:
        if rules_path is None:
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            rules_path = project_root / "data" / "events" / "alias_rules.json"

        self.alias_to_canonical: Dict[str, str] = {}
        self.canonical_to_aliases: Dict[str, List[str]] = {}

        if rules_path.exists():
            with open(rules_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for canonical, aliases in data.items():
                clean_canonical = TitleCleaner.clean(canonical)
                self.canonical_to_aliases[canonical] = []
                
                # The canonical title itself maps to the original canonical title
                self.alias_to_canonical[clean_canonical] = canonical

                for alias in aliases:
                    clean_alias = TitleCleaner.clean(alias)
                    self.alias_to_canonical[clean_alias] = canonical
                    self.canonical_to_aliases[canonical].append(clean_alias)

    def get_aliases(self, canonical_title: str) -> List[str]:
        """Returns the list of cleaned aliases for a given canonical title."""
        canonical = self.get_canonical_title(canonical_title) or canonical_title
        return self.canonical_to_aliases.get(canonical, [])

    def get_canonical_title(self, title: str) -> Optional[str]:
        """Resolves a title (alias or canonical) to its canonical title. Returns None if unknown."""
        clean_title = TitleCleaner.clean(title)
        return self.alias_to_canonical.get(clean_title)
