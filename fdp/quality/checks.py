"""Statistical building blocks for measuring data quality: completeness,
freshness, outlier detection (z-score + IQR, the two classic univariate
methods -- using both catches anomalies whether the series is roughly
normal, like daily returns, or skewed, like YoY growth rates), and
cross-source reconciliation.

Each function returns plain floats/tuples so it's trivially unit-testable
and has no dependency on the ORM or acquisition layers.
"""

from __future__ import annotations

import statistics
from datetime import date
from typing import Dict, List, Optional, Sequence, Tuple

from fdp.quality.constants import (
    IQR_MULTIPLIER,
    OUTLIER_Z_THRESHOLD,
    RECONCILIATION_TOLERANCE,
)


def completeness_score(valid_count: int, total_count: int) -> float:
    if total_count <= 0:
        return 0.0
    return max(0.0, min(1.0, valid_count / total_count))


def freshness_score(latest_date: Optional[date], as_of: date, fresh_days: int, stale_days: int) -> float:
    if latest_date is None:
        return 0.0
    age_days = (as_of - latest_date).days
    if age_days <= fresh_days:
        return 1.0
    if age_days >= stale_days:
        return 0.0
    span = stale_days - fresh_days
    return max(0.0, min(1.0, 1.0 - (age_days - fresh_days) / span))


def _z_scores(values: Sequence[float]) -> List[float]:
    if len(values) < 3:
        return [0.0] * len(values)
    mean = statistics.fmean(values)
    stdev = statistics.pstdev(values)
    if stdev == 0:
        return [0.0] * len(values)
    return [(v - mean) / stdev for v in values]


def _iqr_bounds(values: Sequence[float]) -> Tuple[float, float]:
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    if n < 4:
        return float("-inf"), float("inf")
    q1 = statistics.median(sorted_vals[: n // 2])
    upper_half = sorted_vals[(n + 1) // 2 :]
    q3 = statistics.median(upper_half)
    iqr = q3 - q1
    return q1 - IQR_MULTIPLIER * iqr, q3 + IQR_MULTIPLIER * iqr


def outlier_score(values: Sequence[float]) -> Tuple[float, List[int]]:
    """Returns (score, flagged_indices). A value is flagged if it fails
    *either* the z-score test or the IQR test."""
    values = list(values)
    if len(values) < 3:
        return 1.0, []
    z_scores = _z_scores(values)
    lower, upper = _iqr_bounds(values)
    flagged = [
        idx
        for idx, (val, z) in enumerate(zip(values, z_scores))
        if abs(z) > OUTLIER_Z_THRESHOLD or val < lower or val > upper
    ]
    score = 1.0 - (len(flagged) / len(values))
    return max(0.0, min(1.0, score)), flagged


def reconciliation_score(
    primary: Dict[str, float], secondary: Optional[Dict[str, float]], tolerance: float = RECONCILIATION_TOLERANCE
) -> Tuple[float, bool]:
    """Compares overlapping keys between two sources. Returns (score,
    evaluated). When no second source is available, returns (1.0, False) --
    a caller should record `not_evaluated: true` rather than silently
    treating "no comparison possible" the same as "sources agree perfectly".
    """
    if not secondary:
        return 1.0, False
    shared_keys = set(primary) & set(secondary)
    if not shared_keys:
        return 1.0, False
    diffs = []
    for key in shared_keys:
        a, b = primary[key], secondary[key]
        denom = max(abs(a), abs(b), 1e-9)
        diffs.append(min(1.0, abs(a - b) / denom / tolerance))
    return max(0.0, 1.0 - statistics.fmean(diffs)), True
