"""Combines the individual statistical checks in `checks.py` into one
composite Data Quality score per dataset -- the number that ultimately
becomes the customer-visible "Data Trust Score" attached to every
recommendation.
"""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional, Sequence

from fdp.quality.checks import completeness_score, freshness_score, outlier_score, reconciliation_score
from fdp.quality.constants import DQ_WEIGHTS


def composite_score(
    completeness: float, freshness: float, outlier: float, reconciliation: float,
    weights: Dict[str, float] = DQ_WEIGHTS,
) -> float:
    return (
        weights["completeness"] * completeness
        + weights["freshness"] * freshness
        + weights["outlier"] * outlier
        + weights["reconciliation"] * reconciliation
    )


def score_dataset(
    *,
    valid_count: int,
    total_count: int,
    latest_date: Optional[date],
    as_of: date,
    fresh_days: int,
    stale_days: int,
    outlier_values: Sequence[float],
    secondary_values: Optional[Dict[str, float]] = None,
    primary_values: Optional[Dict[str, float]] = None,
) -> dict:
    """High-level entry point used by the ETL pipeline: given raw ingredients
    for one dataset (prices / income_statement / cash_flow), compute every
    sub-score plus the composite, and a `details` payload worth persisting
    for audit/debugging."""
    completeness = completeness_score(valid_count, total_count)
    freshness = freshness_score(latest_date, as_of, fresh_days, stale_days)
    outlier, flagged_indices = outlier_score(outlier_values)
    reconciliation, evaluated = reconciliation_score(primary_values or {}, secondary_values)

    composite = composite_score(completeness, freshness, outlier, reconciliation)

    return {
        "completeness": completeness,
        "freshness": freshness,
        "outlier": outlier,
        "reconciliation": reconciliation,
        "composite": composite,
        "details": {
            "valid_count": valid_count,
            "total_count": total_count,
            "latest_date": latest_date.isoformat() if latest_date else None,
            "flagged_outlier_indices": flagged_indices,
            "reconciliation_evaluated": evaluated,
        },
    }


def trust_label(score: float) -> str:
    if score >= 0.85:
        return "High"
    if score >= 0.6:
        return "Medium"
    return "Low"
