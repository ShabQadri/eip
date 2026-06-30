"""
Normalizer utility converting parsed feed items into SQLAlchemy database entities.
"""

import hashlib
from typing import Dict, Any
from src.models.article import Article

class ArticleNormalizer:
    """
    Standardizes parsed data formats and generates unique identifier hashes.
    """
    def __init__(self) -> None:
        pass

    def normalize_to_model(
        self, 
        parsed_item: Dict[str, Any], 
        source_id: str, 
        region: str
    ) -> Article:
        """
        Assembles and returns an Article model.
        Generates a SHA-256 hash using the URL to support duplicate protection.
        """
        url = parsed_item.get("url", "")
        
        # Calculate SHA-256 hash of the unique URL string
        url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()

        return Article(
            source_id=source_id,
            title=parsed_item.get("title", ""),
            url=url,
            description=parsed_item.get("description"),
            author=parsed_item.get("author"),
            published_at=parsed_item.get("published_at"),
            hash=url_hash,
            region=region,
            status="new"
        )
