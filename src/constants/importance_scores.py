"""
Scoring criteria and thresholds to determine if a story qualifies for the twice-daily digest.
"""

from typing import Final

# Thresholds
IMPORTANCE_THRESHOLD_DIGEST: Final[float] = 7.0
IMPORTANCE_THRESHOLD_BREAKING: Final[float] = 9.0

# Event Type Weights
WEIGHT_BREAKING_NEWS: Final[float] = 5.0
WEIGHT_EXCLUSIVE: Final[float] = 4.0
WEIGHT_OFFICIAL_TRAILER: Final[float] = 3.0
WEIGHT_CASTING: Final[float] = 2.0
WEIGHT_REVIEW: Final[float] = 1.0

# Source Trust Multipliers
TRUST_MULTIPLIER_HIGH: Final[float] = 1.2
TRUST_MULTIPLIER_STANDARD: Final[float] = 1.0
TRUST_MULTIPLIER_LOW: Final[float] = 0.8
