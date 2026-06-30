"""
Images package for generating dynamic cover cards and social graphics for digests.
"""

from pathlib import Path

class SocialCardGenerator:
    """
    Generates promotional visual cards overlaying digest highlights.
    """
    def __init__(self, output_directory: Path) -> None:
        self.output_directory = output_directory

    def generate_highlight_card(self, title: str, category: str) -> Path:
        """
        Creates a custom graphic saved inside data/images/ and returns the path.
        """
        # Dynamic card creation logic (using Pillow/etc.) goes here
        return self.output_directory / "highlight_placeholder.png"
