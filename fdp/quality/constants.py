"""Re-exported from `fdp.config` so the quality module has one obvious place
to import its tunables from, without every caller reaching into config.py."""

from fdp.config import (
    DQ_WEIGHTS,
    FUNDAMENTAL_FRESH_DAYS,
    FUNDAMENTAL_STALE_DAYS,
    IQR_MULTIPLIER,
    OUTLIER_Z_THRESHOLD,
    PRICE_FRESH_DAYS,
    PRICE_STALE_DAYS,
    RECONCILIATION_TOLERANCE,
)

__all__ = [
    "DQ_WEIGHTS",
    "FUNDAMENTAL_FRESH_DAYS",
    "FUNDAMENTAL_STALE_DAYS",
    "IQR_MULTIPLIER",
    "OUTLIER_Z_THRESHOLD",
    "PRICE_FRESH_DAYS",
    "PRICE_STALE_DAYS",
    "RECONCILIATION_TOLERANCE",
]
