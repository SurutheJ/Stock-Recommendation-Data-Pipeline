"""
Central configuration: database location, data-quality thresholds/weights, and the
"customer profile" weight sets used by the recommendation engine.

Keeping all of this in one module means every tunable knob in the platform —
how quality is scored, how a recommendation is weighted for a given kind of
investor — is visible and auditable in one place, rather than scattered as
magic numbers through the codebase.
"""

from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
FIXTURES_DIR = DATA_DIR / "fixtures"
DEFAULT_DB_PATH = DATA_DIR / "platform.db"
DEFAULT_DB_URL = f"sqlite:///{DEFAULT_DB_PATH}"

# --- Data quality scoring -----------------------------------------------------

DQ_WEIGHTS = {
    "completeness": 0.35,
    "freshness": 0.25,
    "outlier": 0.25,
    "reconciliation": 0.15,
}

OUTLIER_Z_THRESHOLD = 3.0
IQR_MULTIPLIER = 1.5

# freshness decays linearly from 1.0 (at *_FRESH_DAYS or newer) to 0.0 (at *_STALE_DAYS)
PRICE_FRESH_DAYS = 3
PRICE_STALE_DAYS = 30
FUNDAMENTAL_FRESH_DAYS = 100
FUNDAMENTAL_STALE_DAYS = 190

RECONCILIATION_TOLERANCE = 0.02  # 2% relative difference tolerated across sources

# Below this composite data-quality score, a "trust-adjusting" profile will not
# let the engine issue a BUY, however good the underlying financial metrics look.
TRUST_ADJUSTMENT_THRESHOLD = 0.6

# --- Recommendation thresholds -------------------------------------------------

DEFAULT_THRESHOLDS = {"buy": 0.5, "hold": 0.3}

# --- Customer ("investor") profiles -------------------------------------------
# Each profile is a fit-for-purpose lens on the *same* underlying modeled data:
# different customers care about different factors, so the weighting (and, for
# quality_investor, whether a low Data Trust Score can veto a BUY) changes per
# profile rather than the data itself.

INVESTOR_PROFILES = {
    "balanced": {
        "label": "Balanced Investor",
        "description": "The original evenly-weighted rule set: a bit of everything.",
        "weights": {
            "pe_ratio": -0.2,
            "eps_growth": 0.3,
            "revenue_growth": 0.2,
            "free_cash_flow_growth": 0.2,
            "price_vs_50_avg": 0.1,
            "price_vs_200_avg": 0.1,
        },
        "thresholds": DEFAULT_THRESHOLDS,
        "trust_adjustment": False,
    },
    "growth_investor": {
        "label": "Growth Investor",
        "description": "Cares most about how fast revenue, earnings, and cash flow are expanding.",
        "weights": {
            "pe_ratio": -0.05,
            "eps_growth": 0.35,
            "revenue_growth": 0.30,
            "free_cash_flow_growth": 0.20,
            "price_vs_50_avg": 0.05,
            "price_vs_200_avg": 0.05,
        },
        "thresholds": DEFAULT_THRESHOLDS,
        "trust_adjustment": False,
    },
    "value_investor": {
        "label": "Value Investor",
        "description": "Cares most about not overpaying (valuation), growth is secondary.",
        "weights": {
            "pe_ratio": -0.40,
            "eps_growth": 0.10,
            "revenue_growth": 0.10,
            "free_cash_flow_growth": 0.15,
            "price_vs_50_avg": 0.05,
            "price_vs_200_avg": 0.10,
        },
        "thresholds": {"buy": 0.35, "hold": 0.15},
        "trust_adjustment": False,
    },
    "quality_investor": {
        "label": "Quality-Conscious Investor",
        "description": (
            "Balanced financial weighting, but will never accept a BUY built on "
            "data the platform itself doesn't trust."
        ),
        "weights": {
            "pe_ratio": -0.2,
            "eps_growth": 0.3,
            "revenue_growth": 0.2,
            "free_cash_flow_growth": 0.2,
            "price_vs_50_avg": 0.1,
            "price_vs_200_avg": 0.1,
        },
        "thresholds": DEFAULT_THRESHOLDS,
        "trust_adjustment": True,
    },
}

DEFAULT_PROFILE = "balanced"
