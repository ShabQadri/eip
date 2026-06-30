"""
EIP Event Processing and Smart Deduplication Package.
"""

from src.processing.events.title_cleaner import TitleCleaner
from src.processing.events.alias_manager import AliasManager
from src.processing.events.franchise_detector import FranchiseDetector
from src.processing.events.similarity_engine import SimilarityEngine
from src.processing.events.event_matcher import EventMatcher
from src.processing.events.event_builder import EventBuilder
from src.processing.events.event_service import EventService

__all__ = [
    "TitleCleaner",
    "AliasManager",
    "FranchiseDetector",
    "SimilarityEngine",
    "EventMatcher",
    "EventBuilder",
    "EventService",
]
