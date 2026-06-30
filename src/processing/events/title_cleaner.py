"""
Title cleaning and normalization utility.
"""

import re
import unicodedata

class TitleCleaner:
    """
    Normalizes titles to resolve differences in punctuation, casing, spacing, and sequel numbering.
    """
    @staticmethod
    def clean(title: str) -> str:
        if not title:
            return ""

        # 1. Lowercase
        t = title.lower()

        # 2. Unicode Normalization (NFKD) and ASCII fallback
        t = unicodedata.normalize("NFKD", t)
        t = "".join(c for c in t if not unicodedata.combining(c))

        # 3. Standardize sequel representations
        # Replace word representation of numbers
        t = re.sub(r"\bpart\s+one\b", "part 1", t)
        t = re.sub(r"\bpart\s+two\b", "part 2", t)
        t = re.sub(r"\bpart\s+three\b", "part 3", t)
        
        # Replace Roman numerals associated with 'part'
        t = re.sub(r"\bpart\s+iii\b", "part 3", t)
        t = re.sub(r"\bpart\s+ii\b", "part 2", t)
        t = re.sub(r"\bpart\s+i\b", "part 1", t)

        # Replace standalone Roman numerals at the end or boundary
        t = re.sub(r"\biii\b", "3", t)
        t = re.sub(r"\bii\b", "2", t)
        # Avoid replacing standalone 'i' which might be the pronoun, only replace if trailing number indicator
        # but in titles, "part i" is handled above. Let's do trailing ' i'
        t = re.sub(r"\s+i\b", " 1", t)

        # 4. Remove punctuation (except alphanumeric characters and spaces)
        t = re.sub(r"[^\w\s]", " ", t)

        # 5. Collapse multiple whitespaces and strip
        t = re.sub(r"\s+", " ", t)
        t = t.strip()

        return t
