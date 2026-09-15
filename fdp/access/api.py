"""A small FastAPI service exposing the modeled data, its quality scores,
and profile-weighted recommendations as queryable "data products" -- so the
same governed dataset is accessible to more than one client.

`create_app(session_factory)` is a factory rather than a bare module-level
`app` so tests can point it at an isolated in-memory database; a default
`app` is still exposed for `uvicorn fdp.access.api:app`.
"""

from __future__ import annotations

import statistics
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from fdp.config import DEFAULT_PROFILE, INVESTOR_PROFILES
from fdp.modeling import repository as repo
from fdp.modeling.orm_models import CashFlowPeriod, Company, IncomeStatementPeriod, PriceObservation
from fdp.recommend.engine import generate_recommendation


def create_app(session_factory: sessionmaker) -> FastAPI:
    app = FastAPI(
        title="Trade Signal Platform API",
        description="Modeled financial data, data-quality scores, and profile-weighted recommendations.",
    )

    def get_session():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def _company_or_404(session, ticker: str) -> Company:
        company = repo.get_company_by_ticker(session, ticker)
        if company is None:
            raise HTTPException(status_code=404, detail=f"Unknown ticker '{ticker.upper()}'")
        return company

    @app.get("/companies")
    def list_companies(session=Depends(get_session)):
        companies = session.execute(select(Company)).scalars().all()
        return [
            {"ticker": c.ticker, "name": c.name, "sector": c.sector, "industry": c.industry}
            for c in companies
        ]

    @app.get("/companies/{ticker}/prices")
    def get_prices(ticker: str, session=Depends(get_session)):
        company = _company_or_404(session, ticker)
        rows = (
            session.execute(
                select(PriceObservation)
                .where(PriceObservation.company_id == company.id)
                .order_by(PriceObservation.date)
            )
            .scalars()
            .all()
        )
        return [
            {
                "date": r.date.isoformat(),
                "open": r.open,
                "high": r.high,
                "low": r.low,
                "close": r.close,
                "volume": r.volume,
                "source": r.source,
            }
            for r in rows
        ]

    @app.get("/companies/{ticker}/fundamentals")
    def get_fundamentals(ticker: str, session=Depends(get_session)):
        company = _company_or_404(session, ticker)
        income = (
            session.execute(
                select(IncomeStatementPeriod)
                .where(IncomeStatementPeriod.company_id == company.id)
                .order_by(IncomeStatementPeriod.period_end_date)
            )
            .scalars()
            .all()
        )
        cash_flow = (
            session.execute(
                select(CashFlowPeriod)
                .where(CashFlowPeriod.company_id == company.id)
                .order_by(CashFlowPeriod.period_end_date)
            )
            .scalars()
            .all()
        )
        return {
            "income_statements": [
                {
                    "period_end_date": r.period_end_date.isoformat(),
                    "fiscal_year": r.fiscal_year,
                    "revenue": r.revenue,
                    "net_income": r.net_income,
                    "eps_diluted": r.eps_diluted,
                }
                for r in income
            ],
            "cash_flows": [
                {
                    "period_end_date": r.period_end_date.isoformat(),
                    "fiscal_year": r.fiscal_year,
                    "operating_cash_flow": r.operating_cash_flow,
                    "capital_expenditures": r.capital_expenditures,
                    "free_cash_flow": r.free_cash_flow,
                }
                for r in cash_flow
            ],
        }

    @app.get("/companies/{ticker}/derived-metrics")
    def get_derived_metrics(ticker: str, session=Depends(get_session)):
        _company_or_404(session, ticker)
        return repo.get_derived_metrics(session, ticker)

    @app.get("/companies/{ticker}/quality")
    def get_quality(ticker: str, session=Depends(get_session)):
        _company_or_404(session, ticker)
        scores = repo.get_latest_quality_scores(session, ticker)
        return {
            dataset: {
                "completeness": s.completeness_score,
                "freshness": s.freshness_score,
                "outlier": s.outlier_score,
                "reconciliation": s.reconciliation_score,
                "composite": s.composite_score,
            }
            for dataset, s in scores.items()
        }

    @app.get("/companies/{ticker}/recommendation")
    def get_recommendation(
        ticker: str,
        profile: str = Query(default=DEFAULT_PROFILE, enum=list(INVESTOR_PROFILES)),
        session=Depends(get_session),
    ):
        _company_or_404(session, ticker)
        metrics = repo.get_derived_metrics(session, ticker)
        quality = repo.get_latest_quality_scores(session, ticker)
        if not metrics or not quality:
            raise HTTPException(status_code=404, detail=f"No ingested data for '{ticker.upper()}' yet")
        data_trust_score = statistics.fmean(s.composite_score for s in quality.values())
        rec = generate_recommendation(ticker.upper(), metrics, data_trust_score, profile)
        return {
            "ticker": rec.ticker,
            "profile": rec.profile,
            "profile_label": rec.profile_label,
            "verdict": rec.verdict,
            "weighted_score": rec.weighted_score,
            "data_trust_score": rec.data_trust_score,
            "data_trust_label": rec.data_trust_label,
            "reasoning": rec.reasoning,
        }

    @app.get("/runs/{run_id}")
    def get_run(run_id: str, session=Depends(get_session)):
        entries = repo.get_run_log(session, run_id)
        if not entries:
            raise HTTPException(status_code=404, detail=f"Unknown run_id '{run_id}'")
        return [
            {
                "stage": e.stage,
                "status": e.status,
                "started_at": e.started_at.isoformat(),
                "finished_at": e.finished_at.isoformat() if e.finished_at else None,
                "rows_processed": e.rows_processed,
                "error_message": e.error_message,
            }
            for e in entries
        ]

    return app


def __getattr__(name: str):
    # Lazily builds a default, file-backed `app` only when actually accessed
    # (e.g. `uvicorn fdp.access.api:app`), so merely importing this module
    # (as tests do, via `create_app`) never touches disk as a side effect.
    if name == "app":
        from fdp.modeling.database import build_default_session_factory

        return create_app(build_default_session_factory())
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
