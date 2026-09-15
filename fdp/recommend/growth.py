"""Year-over-year growth math -- the same formula from the original concept
(`growth = (latest - previous) / previous`), with a guard for a zero or
missing prior-year value so a single bad denominator can't blow up the
whole recommendation.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple


def yoy_growth(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if current is None or previous is None or previous == 0:
        return None
    return (current - previous) / previous


def growth_series(values_by_period: Sequence[Tuple[object, Optional[float]]]) -> List[Tuple[object, Optional[float]]]:
    """Given [(period_key, value), ...] sorted ascending by period, return
    [(period_key, growth_vs_prior_period), ...] for periods 2..N."""
    out: List[Tuple[object, Optional[float]]] = []
    for i in range(1, len(values_by_period)):
        period_key, current = values_by_period[i]
        _, previous = values_by_period[i - 1]
        out.append((period_key, yoy_growth(current, previous)))
    return out


def simple_moving_average(values: Sequence[float], window: int) -> Optional[float]:
    if len(values) < window or window <= 0:
        return None
    return sum(values[-window:]) / window
