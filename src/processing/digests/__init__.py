"""
Digest generation package initialization.
"""

from src.processing.digests.breaking_detector import BreakingDetector
from src.processing.digests.digest_selector import DigestSelector
from src.processing.digests.digest_formatter import DigestFormatter
from src.processing.digests.telegram_formatter import TelegramFormatter
from src.processing.digests.digest_service import DigestService

__all__ = [
    "BreakingDetector",
    "DigestSelector",
    "DigestFormatter",
    "TelegramFormatter",
    "DigestService",
]
