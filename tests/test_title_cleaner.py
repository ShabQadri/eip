"""
Unit tests for the TitleCleaner class.
"""

from src.processing.events.title_cleaner import TitleCleaner

def test_title_cleaner_normalization() -> None:
    # Casing, spacing, and punctuation
    assert TitleCleaner.clean("Dune: Messiah") == "dune messiah"
    assert TitleCleaner.clean("  Dune   Messiah  ") == "dune messiah"
    assert TitleCleaner.clean("Dune Messiah!!!") == "dune messiah"
    
    # Unicode / Accent normalization
    assert TitleCleaner.clean("Café") == "cafe"

    # Part & Roman numeral conversions
    assert TitleCleaner.clean("Dune Part Three") == "dune part 3"
    assert TitleCleaner.clean("Dune Part III") == "dune part 3"
    assert TitleCleaner.clean("Dune Part ii") == "dune part 2"
    assert TitleCleaner.clean("Avengers 3") == "avengers 3"
    assert TitleCleaner.clean("Avengers iii") == "avengers 3"
    assert TitleCleaner.clean("Avengers Part i") == "avengers part 1"
    assert TitleCleaner.clean("War i") == "war 1"
