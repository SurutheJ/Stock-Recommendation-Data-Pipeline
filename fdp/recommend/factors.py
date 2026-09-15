"""Normalizes raw derived metrics (a P/E ratio, a growth rate, a price vs.
moving-average ratio) into a 0-1 factor score, so the recommendation
engine's weighted sum is always combining like-with-like.

Each normalization is a simple, documented linear clamp -- deliberately not
a black box, since a data-management customer should be able to see exactly
why a factor scored the way it did.
"""

from __future__ import annotations

from typing import Optional


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def normalize_growth_score(growth: Optional[float], floor: float = -0.20, cap: float = 0.20) -> float:
    """-20% growth or worse -> 0.0, +20% growth or better -> 1.0, linear between.
    Missing data scores a neutral 0.5 rather than penalizing or rewarding it --
    the Data Trust Score is what should flag missing data, not this score."""
    if growth is None:
        return 0.5
    return _clamp((growth - floor) / (cap - floor))


def normalize_pe_score(pe_ratio: Optional[float], cheap: float = 5.0, expensive: float = 40.0) -> float:
    """Higher P/E -> higher score here (i.e. "more expensive"); the engine's
    negative weight on this factor is what turns "expensive" into a penalty."""
    if pe_ratio is None or pe_ratio <= 0:
        return 0.5
    return _clamp((pe_ratio - cheap) / (expensive - cheap))


def normalize_price_vs_avg_score(price: Optional[float], moving_average: Optional[float]) -> float:
    """Price at 90% of its moving average or below -> 0.0 (bearish), at 110%
    or above -> 1.0 (bullish momentum), linear between."""
    if price is None or moving_average is None or moving_average <= 0:
        return 0.5
    ratio = price / moving_average
    return _clamp((ratio - 0.90) / 0.20)
