"""The customer-facing recommendation engine.

This is the same weighted-scoring idea from the original concept notebook,
but: (1) the weights come from a chosen "customer profile" (growth / value /
quality-conscious investor) instead of one fixed rule set, and (2) every
verdict is returned alongside the Data Trust Score of the dataset it was
computed from, so a low-quality dataset visibly caveats the recommendation
instead of producing an equally confident-looking Buy/Sell either way.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from fdp.config import (
    DEFAULT_PROFILE,
    INVESTOR_PROFILES,
    TRUST_ADJUSTMENT_THRESHOLD,
)
from fdp.quality.scoring import trust_label
from fdp.recommend.factors import (
    normalize_growth_score,
    normalize_pe_score,
    normalize_price_vs_avg_score,
)


@dataclass
class Recommendation:
    ticker: str
    profile: str
    profile_label: str
    verdict: str
    weighted_score: float
    factor_scores: Dict[str, float] = field(default_factory=dict)
    factor_contributions: Dict[str, float] = field(default_factory=dict)
    data_trust_score: float = 1.0
    data_trust_label: str = "High"
    reasoning: str = ""
    trust_adjusted: bool = False


def _factor_scores(metrics: Dict[str, Optional[float]]) -> Dict[str, float]:
    return {
        "pe_ratio": normalize_pe_score(metrics.get("pe_ratio")),
        "eps_growth": normalize_growth_score(metrics.get("eps_yoy_growth")),
        "revenue_growth": normalize_growth_score(metrics.get("revenue_yoy_growth")),
        "free_cash_flow_growth": normalize_growth_score(metrics.get("fcf_yoy_growth")),
        "price_vs_50_avg": normalize_price_vs_avg_score(
            metrics.get("latest_close"), metrics.get("sma_50")
        ),
        "price_vs_200_avg": normalize_price_vs_avg_score(
            metrics.get("latest_close"), metrics.get("sma_200")
        ),
    }


def _classify(score: float, thresholds: Dict[str, float]) -> str:
    if score >= thresholds["buy"]:
        return "BUY"
    if score >= thresholds["hold"]:
        return "HOLD"
    return "SELL"


def _build_reasoning(
    ticker: str,
    verdict: str,
    contributions: Dict[str, float],
    metrics: Dict[str, Optional[float]],
    data_trust_score: float,
    trust_adjusted: bool,
) -> str:
    top_factors = sorted(contributions.items(), key=lambda kv: abs(kv[1]), reverse=True)[:3]
    factor_phrases = []
    labels = {
        "pe_ratio": "valuation (P/E)",
        "eps_growth": "EPS growth",
        "revenue_growth": "revenue growth",
        "free_cash_flow_growth": "free cash flow growth",
        "price_vs_50_avg": "price vs. 50-day average",
        "price_vs_200_avg": "price vs. 200-day average",
    }
    for name, contribution in top_factors:
        direction = "supporting" if contribution >= 0 else "weighing against"
        factor_phrases.append(f"{labels.get(name, name)} ({direction} the call)")

    reasoning = (
        f"{ticker}: {verdict}, driven mainly by {', '.join(factor_phrases)}. "
        f"Data Trust Score {data_trust_score:.2f} ({trust_label(data_trust_score)})."
    )
    if trust_adjusted:
        reasoning += (
            " The underlying data quality was too low to support a BUY, "
            "so this profile capped the verdict at HOLD."
        )
    return reasoning


def generate_recommendation(
    ticker: str,
    metrics: Dict[str, Optional[float]],
    data_trust_score: float,
    profile_name: str = DEFAULT_PROFILE,
) -> Recommendation:
    profile = INVESTOR_PROFILES[profile_name]
    weights = profile["weights"]
    thresholds = profile["thresholds"]

    factor_scores = _factor_scores(metrics)
    contributions = {name: weights[name] * factor_scores[name] for name in weights}
    weighted_score = sum(contributions.values())

    verdict = _classify(weighted_score, thresholds)

    trust_adjusted = False
    if profile.get("trust_adjustment") and data_trust_score < TRUST_ADJUSTMENT_THRESHOLD and verdict == "BUY":
        verdict = "HOLD"
        trust_adjusted = True

    reasoning = _build_reasoning(
        ticker, verdict, contributions, metrics, data_trust_score, trust_adjusted
    )

    return Recommendation(
        ticker=ticker,
        profile=profile_name,
        profile_label=profile["label"],
        verdict=verdict,
        weighted_score=weighted_score,
        factor_scores=factor_scores,
        factor_contributions=contributions,
        data_trust_score=data_trust_score,
        data_trust_label=trust_label(data_trust_score),
        reasoning=reasoning,
        trust_adjusted=trust_adjusted,
    )
