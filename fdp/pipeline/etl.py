"""The ETL orchestrator: acquire -> validate -> load -> derive -> score
quality -> recommend -> finalize. Every stage is logged (correlated by
`run_id`) to `PipelineRunLog`, and every write is an idempotent upsert, so
running this twice for the same ticker refreshes rather than duplicates
data -- see `tests/test_pipeline_idempotency.py`.
"""

from __future__ import annotations

import statistics
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, Optional

from sqlalchemy.orm import sessionmaker

from fdp.acquisition.base import AbstractMarketDataClient
from fdp.config import (
    DEFAULT_PROFILE,
    FUNDAMENTAL_FRESH_DAYS,
    FUNDAMENTAL_STALE_DAYS,
    PRICE_FRESH_DAYS,
    PRICE_STALE_DAYS,
)
from fdp.modeling import repository as repo
from fdp.pipeline.logging_config import get_logger
from fdp.pipeline.retry import retry_with_backoff
from fdp.quality.scoring import score_dataset
from fdp.recommend.engine import Recommendation, generate_recommendation
from fdp.recommend.growth import growth_series, simple_moving_average, yoy_growth
from fdp.validation.business_rules import check_cash_flows, check_income_statements, check_prices
from fdp.validation.models import (
    validate_cash_flows,
    validate_company_profile,
    validate_income_statements,
    validate_price_bars,
)

logger = get_logger("fdp.pipeline")


class PipelineError(RuntimeError):
    """Raised when a pipeline stage fails unrecoverably."""


@dataclass
class PipelineResult:
    run_id: str
    ticker: str
    rows_processed: Dict[str, int] = field(default_factory=dict)
    rejected_counts: Dict[str, int] = field(default_factory=dict)
    warnings: Dict[str, list] = field(default_factory=dict)
    quality_scores: Dict[str, dict] = field(default_factory=dict)
    recommendation: Optional[Recommendation] = None


def _log(session_factory: sessionmaker, run_id: str, ticker: str, stage: str, status: str, **kwargs) -> None:
    with session_factory() as session:
        repo.log_pipeline_stage(session, run_id, ticker, stage, status, **kwargs)
        session.commit()
    logger.info(
        f"stage={stage} status={status}",
        extra={"run_id": run_id, "ticker": ticker, "stage": stage, "status": status},
    )


@retry_with_backoff(max_attempts=3, base_delay_seconds=0.2)
def _acquire(client: AbstractMarketDataClient, ticker: str):
    profile = client.get_company_profile(ticker)
    prices = client.get_prices(ticker)
    income = client.get_income_statements(ticker)
    cash_flow = client.get_cash_flows(ticker)
    return profile, prices, income, cash_flow


def run_pipeline(
    ticker: str,
    client: AbstractMarketDataClient,
    session_factory: sessionmaker,
    profile_name: str = DEFAULT_PROFILE,
    as_of: Optional[date] = None,
) -> PipelineResult:
    ticker = ticker.upper()
    run_id = str(uuid.uuid4())
    as_of = as_of or date.today()
    result = PipelineResult(run_id=run_id, ticker=ticker)

    # --- 1. Acquire -----------------------------------------------------
    _log(session_factory, run_id, ticker, "acquisition", "running")
    try:
        raw_profile, raw_prices, raw_income, raw_cash_flow = _acquire(client, ticker)
    except Exception as exc:
        _log(session_factory, run_id, ticker, "acquisition", "failed", error_message=str(exc))
        raise PipelineError(f"acquisition failed for {ticker}: {exc}") from exc
    total_rows = len(raw_prices) + len(raw_income) + len(raw_cash_flow)
    _log(session_factory, run_id, ticker, "acquisition", "success", rows_processed=total_rows)

    # --- 2. Validate ------------------------------------------------------
    validated_profile = validate_company_profile(raw_profile)
    valid_prices, rejected_prices = validate_price_bars(raw_prices)
    valid_income, rejected_income = validate_income_statements(raw_income)
    valid_cash_flow, rejected_cash_flow = validate_cash_flows(raw_cash_flow)
    valid_prices.sort(key=lambda r: r.date)
    valid_income.sort(key=lambda r: r.period_end_date)
    valid_cash_flow.sort(key=lambda r: r.period_end_date)

    result.rejected_counts = {
        "prices": len(rejected_prices),
        "income_statement": len(rejected_income),
        "cash_flow": len(rejected_cash_flow),
    }
    _log(
        session_factory,
        run_id,
        ticker,
        "validation",
        "success",
        rows_processed=len(valid_prices) + len(valid_income) + len(valid_cash_flow),
    )

    # --- 3. Business rules (soft warnings, do not reject) ------------------
    result.warnings = {
        "prices": check_prices(valid_prices).warnings,
        "income_statement": check_income_statements(valid_income).warnings,
        "cash_flow": check_cash_flows(valid_cash_flow).warnings,
    }

    # --- 4. Load (idempotent upserts) --------------------------------------
    with session_factory() as session:
        company = repo.get_or_create_company(session, validated_profile)
        n_prices = repo.upsert_price_observations(session, company, valid_prices, client.source_name)
        n_income = repo.upsert_income_statements(session, company, valid_income, client.source_name)
        n_cash_flow = repo.upsert_cash_flows(session, company, valid_cash_flow, client.source_name)
        session.commit()
    result.rows_processed = {"prices": n_prices, "income_statement": n_income, "cash_flow": n_cash_flow}
    _log(session_factory, run_id, ticker, "load", "success", rows_processed=n_prices + n_income + n_cash_flow)

    # --- 5. Derive metrics (the cross-dataset join point) -------------------
    closes = [p.close for p in valid_prices]
    latest_close = closes[-1] if closes else None
    sma_50 = simple_moving_average(closes, 50)
    sma_200 = simple_moving_average(closes, 200)

    income_by_year = [(r.fiscal_year, r) for r in valid_income]
    revenue_growth = growth_series([(y, r.revenue) for y, r in income_by_year])
    net_income_growth = growth_series([(y, r.net_income) for y, r in income_by_year])
    eps_growth = growth_series([(y, r.eps_diluted) for y, r in income_by_year])
    fcf_growth = growth_series([(r.fiscal_year, r.free_cash_flow) for r in valid_cash_flow])

    latest_eps = valid_income[-1].eps_diluted if valid_income else None
    pe_ratio = (latest_close / latest_eps) if (latest_close and latest_eps and latest_eps > 0) else None

    derived_as_of = valid_prices[-1].date if valid_prices else as_of
    metrics: Dict[str, Optional[float]] = {
        "latest_close": latest_close,
        "sma_50": sma_50,
        "sma_200": sma_200,
        "pe_ratio": pe_ratio,
        "revenue_yoy_growth": revenue_growth[-1][1] if revenue_growth else None,
        "net_income_yoy_growth": net_income_growth[-1][1] if net_income_growth else None,
        "eps_yoy_growth": eps_growth[-1][1] if eps_growth else None,
        "fcf_yoy_growth": fcf_growth[-1][1] if fcf_growth else None,
    }
    with session_factory() as session:
        company = repo.get_company_by_ticker(session, ticker)
        for name, value in metrics.items():
            if value is not None:
                repo.upsert_derived_metric(session, company, name, derived_as_of, value)
        session.commit()
    _log(session_factory, run_id, ticker, "derive", "success", rows_processed=sum(v is not None for v in metrics.values()))

    # --- 6. Score data quality per dataset -----------------------------------
    price_returns = [
        (b - a) / a for a, b in zip(closes, closes[1:]) if a
    ]
    price_quality = score_dataset(
        valid_count=len(valid_prices),
        total_count=len(raw_prices),
        latest_date=valid_prices[-1].date if valid_prices else None,
        as_of=as_of,
        fresh_days=PRICE_FRESH_DAYS,
        stale_days=PRICE_STALE_DAYS,
        outlier_values=price_returns,
    )
    income_growth_values = [g for _, g in revenue_growth + eps_growth if g is not None]
    income_quality = score_dataset(
        valid_count=len(valid_income),
        total_count=len(raw_income),
        latest_date=valid_income[-1].period_end_date if valid_income else None,
        as_of=as_of,
        fresh_days=FUNDAMENTAL_FRESH_DAYS,
        stale_days=FUNDAMENTAL_STALE_DAYS,
        outlier_values=income_growth_values,
    )
    cash_flow_quality = score_dataset(
        valid_count=len(valid_cash_flow),
        total_count=len(raw_cash_flow),
        latest_date=valid_cash_flow[-1].period_end_date if valid_cash_flow else None,
        as_of=as_of,
        fresh_days=FUNDAMENTAL_FRESH_DAYS,
        stale_days=FUNDAMENTAL_STALE_DAYS,
        outlier_values=[g for _, g in fcf_growth if g is not None],
    )

    result.quality_scores = {
        "prices": price_quality,
        "income_statement": income_quality,
        "cash_flow": cash_flow_quality,
    }
    with session_factory() as session:
        company = repo.get_company_by_ticker(session, ticker)
        for dataset_name, scores in result.quality_scores.items():
            repo.record_quality_score(session, company, run_id, dataset_name, scores)
        session.commit()
    _log(session_factory, run_id, ticker, "quality", "success", rows_processed=len(result.quality_scores))

    # --- 7. Recommend ---------------------------------------------------------
    data_trust_score = statistics.fmean(s["composite"] for s in result.quality_scores.values())
    result.recommendation = generate_recommendation(ticker, metrics, data_trust_score, profile_name)
    _log(session_factory, run_id, ticker, "recommend", "success")

    _log(session_factory, run_id, ticker, "pipeline", "success")
    return result
