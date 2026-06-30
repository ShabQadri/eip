import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from rapidfuzz import fuzz
from src.processing.events.title_cleaner import TitleCleaner
from src.processing.events.alias_manager import AliasManager
from src.processing.events.franchise_detector import FranchiseDetector

class SimilarityEngine:
    """
    Evaluates similarity score between two articles or titles.
    Supports exact, alias, fuzzy, and franchise/pattern-driven matching.
    """
    def __init__(
        self, 
        alias_manager: AliasManager, 
        patterns_path: Optional[Path] = None
    ) -> None:
        self.alias_manager = alias_manager
        
        if patterns_path is None:
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            patterns_path = project_root / "data" / "events" / "event_patterns.json"

        self.patterns: Dict[str, List[str]] = {}
        if patterns_path.exists():
            with open(patterns_path, "r", encoding="utf-8") as f:
                self.patterns = json.load(f)

    def detect_pattern(self, title: str, description: str = "") -> Optional[str]:
        """Scans title and description for event pattern keywords."""
        text = f"{title or ''} {description or ''}".lower()
        for pattern_name, keywords in self.patterns.items():
            for kw in keywords:
                if kw.lower() in text:
                    return pattern_name
        return None

    def extract_core_title(self, title: str) -> str:
        """Removes event pattern keywords, review terms, and standard stop words to isolate the core entity name."""
        t = (title or "").lower()
        
        # 1. Remove parenthesized content (e.g. scores like (9/10) or [90%])
        t = re.sub(r"\(.*?\)", " ", t)
        t = re.sub(r"\[.*?\]", " ", t)
        
        # 2. Strip all pattern keywords
        for pattern_name, keywords in self.patterns.items():
            for kw in keywords:
                pattern = re.compile(rf"\b{re.escape(kw.lower())}\b", re.IGNORECASE)
                t = pattern.sub(" ", t)
        
        # 3. Strip review and score keywords
        for kw in ["review", "rating", "score", "masterpiece", "consensus"]:
            pattern = re.compile(rf"\b{kw}\b", re.IGNORECASE)
            t = pattern.sub(" ", t)

        # 4. Strip standard action prepositions and articles
        for word in ["on", "for", "in", "at", "to", "first", "official", "the", "starts", "begins", "enters", "starts", "confirmed", "confirm", "confirms", "reported", "joins", "star", "stars"]:
            t = re.sub(rf"\b{word}\b", " ", t)

        # 4b. Strip season references
        t = re.sub(r"\bseason\s*\d+\b", " ", t)
        t = re.sub(r"\bseason\s+(?:one|two|three|four|five|six|seven|eight|nine|ten)\b", " ", t)

        # 5. Handle separators (split by - or | and take the first part if it is substantial)
        for sep in [" - ", " | "]:
            if sep in title:
                parts = title.split(sep)
                first_part_clean = self.extract_core_title(parts[0])
                if len(first_part_clean.strip()) > 3:
                    return first_part_clean

        # Collapse multiple whitespaces
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def extract_season_and_year(self, title: str, description: str = "") -> tuple[Optional[int], Optional[int]]:
        """Extracts season number and event year from title and description."""
        text = f"{title or ''} {description or ''}".lower()
        
        # 1. Extract season number
        season_num = None
        season_match = re.search(r"\bseason\s*(\d+)\b", text)
        if season_match:
            season_num = int(season_match.group(1))
        else:
            # Check word-based season numbers
            words_map = {
                "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
            }
            for word, val in words_map.items():
                if re.search(r"\bseason\s+" + word + r"\b", text):
                    season_num = val
                    break
                    
        # 2. Extract year (typically 4 digits starting with 20 or 19)
        event_yr = None
        # Try parenthesized year first
        year_match_paren = re.search(r"\((20\d{2}|19\d{2})\)", text)
        if year_match_paren:
            event_yr = int(year_match_paren.group(1))
        else:
            # Fallback to any 4-digit number
            year_match = re.search(r"\b(20\d{2}|19\d{2})\b", text)
            if year_match:
                event_yr = int(year_match.group(1))
                
        return season_num, event_yr

    def calculate_similarity(
        self, 
        title1: str, 
        title2: str,
        desc1: str = "",
        desc2: str = "",
        franchise1: Optional[str] = None,
        franchise2: Optional[str] = None,
        pattern1: Optional[str] = None,
        pattern2: Optional[str] = None
    ) -> float:
        """
        Calculates a similarity score in the range [0, 100].
        - Exact Match: 100
        - Alias Match: 100
        - Fuzzy Matching (RapidFuzz token_sort_ratio) + Heuristic Franchise/Pattern bonus (+10)
        """
        # Detect patterns if not provided
        if pattern1 is None:
            pattern1 = self.detect_pattern(title1, desc1)
        if pattern2 is None:
            pattern2 = self.detect_pattern(title2, desc2)

        # Hardening rule: different event patterns must never merge
        if pattern1 and pattern2 and pattern1 != pattern2:
            return 0.0

        # Hardening rule: different season numbers or event years must never merge
        # but only for TV lifecycle/renewal events (where year/season is a true differentiator)
        is_tv_lifecycle = (
            pattern1 in ["RENEWAL", "SEASON_ANNOUNCEMENT"] or
            pattern2 in ["RENEWAL", "SEASON_ANNOUNCEMENT"]
        )
        if is_tv_lifecycle:
            s_num1, yr1 = self.extract_season_and_year(title1, desc1)
            s_num2, yr2 = self.extract_season_and_year(title2, desc2)
            if s_num1 is not None and s_num2 is not None and s_num1 != s_num2:
                return 0.0
            if yr1 is not None and yr2 is not None and yr1 != yr2:
                return 0.0

        # Extract core titles (remove event patterns and prepositions)
        core1 = self.extract_core_title(title1)
        core2 = self.extract_core_title(title2)

        clean1 = TitleCleaner.clean(core1)
        clean2 = TitleCleaner.clean(core2)

        # Hardening rule: if both titles contain digit sequences and they don't match, they must never merge
        nums1 = set(re.findall(r"\b\d+\b", clean1))
        nums2 = set(re.findall(r"\b\d+\b", clean2))
        if nums1 and nums2 and nums1 != nums2:
            return 0.0

        # 1. Exact Cleaned Match
        if clean1 == clean2:
            return 100.0

        # 2. Alias Match
        canonical1 = self.alias_manager.get_canonical_title(clean1)
        canonical2 = self.alias_manager.get_canonical_title(clean2)
        if canonical1 and canonical2 and canonical1 == canonical2:
            return 100.0

        # 3. Fuzzy Match via RapidFuzz
        score = fuzz.token_sort_ratio(clean1, clean2)

        # 4. Franchise + Event Pattern Bonus
        if franchise1 and franchise2 and franchise1 == franchise2:
            if pattern1 and pattern2 and pattern1 == pattern2:
                score += 10.0

        # Cap similarity score at 100
        return min(100.0, score)
