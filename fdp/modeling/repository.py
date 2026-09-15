"""The data-access layer: every write is an idempotent upsert keyed on the
unique constraints defined in `orm_models.py`, so re-running the ETL
pipeline for the same ticker/period never creates duplicate rows -- it just
refreshes them. This is what the pipeline idempotency test exercises.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from fdp.modeling.orm_models import (
    CashFlowPeriod,
    Company,
    DataQualityScore,
    DerivedMetric,
    IncomeStatementPeriod,
    PipelineRunLog,
    PriceObservation,
)
from fdp.validation.models import (
    ValidatedCashFlowRow,
    ValidatedCompanyProfile,
    ValidatedIncomeStatementRow,
    ValidatedPriceBar,
)


def get_or_create_company(session: Session, profile: ValidatedCompanyProfile) -> Company:
    company = session.execute(
        select(Company).where(Company.ticker == profile.ticker)
    ).scalar_one_or_none()
    if company is None:
        company = Company(
            ticker=profile.ticker,
            name=profile.name,
            sector=profile.sector,
            industry=profile.industry,
            currency=profile.currency,
        )
        session.add(company)
        session.flush()
    else:
        company.name = profile.name
        company.sector = profile.sector
        company.industry = profile.industry
        company.currency = profile.currency
        company.updated_at = datetime.utcnow()
    return company


def get_company_by_ticker(session: Session, ticker: str) -> Optional[Company]:
    return session.execute(
        select(Company).where(Company.ticker == ticker.upper())
    ).scalar_one_or_none()


def upsert_price_observations(
    session: Session, company: Company, bars: Sequence[ValidatedPriceBar], source: str
) -> int:
    count = 0
    for bar in bars:
        existing = session.execute(
            select(PriceObservation).where(
                PriceObservation.company_id == company.id, PriceObservation.date == bar.date
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = PriceObservation(company_id=company.id, date=bar.date, source=source)
            session.add(existing)
        existing.open = bar.open
        existing.high = bar.high
        existing.low = bar.low
        existing.close = bar.close
        existing.adj_close = bar.adj_close
        existing.volume = bar.volume
        existing.source = source
        existing.ingested_at = datetime.utcnow()
        count += 1
    session.flush()
    return count


def upsert_income_statements(
    session: Session,
    company: Company,
    rows: Sequence[ValidatedIncomeStatementRow],
    source: str,
) -> int:
    count = 0
    for row in rows:
        existing = session.execute(
            select(IncomeStatementPeriod).where(
                IncomeStatementPeriod.company_id == company.id,
                IncomeStatementPeriod.period_end_date == row.period_end_date,
                IncomeStatementPeriod.period_type == row.period_type,
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = IncomeStatementPeriod(
                company_id=company.id,
                period_end_date=row.period_end_date,
                period_type=row.period_type,
                source=source,
            )
            session.add(existing)
        existing.fiscal_year = row.fiscal_year
        existing.revenue = row.revenue
        existing.net_income = row.net_income
        existing.eps_diluted = row.eps_diluted
        existing.operating_income = row.operating_income
        existing.source = source
        existing.ingested_at = datetime.utcnow()
        count += 1
    session.flush()
    return count


def upsert_cash_flows(
    session: Session, company: Company, rows: Sequence[ValidatedCashFlowRow], source: str
) -> int:
    count = 0
    for row in rows:
        existing = session.execute(
            select(CashFlowPeriod).where(
                CashFlowPeriod.company_id == company.id,
                CashFlowPeriod.period_end_date == row.period_end_date,
                CashFlowPeriod.period_type == row.period_type,
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = CashFlowPeriod(
                company_id=company.id,
                period_end_date=row.period_end_date,
                period_type=row.period_type,
                source=source,
            )
            session.add(existing)
        existing.fiscal_year = row.fiscal_year
        existing.operating_cash_flow = row.operating_cash_flow
        existing.capital_expenditures = row.capital_expenditures
        existing.free_cash_flow = row.free_cash_flow
        existing.source = source
        existing.ingested_at = datetime.utcnow()
        count += 1
    session.flush()
    return count


def upsert_derived_metric(
    session: Session, company: Company, metric_name: str, as_of_date, value: float
) -> None:
    existing = session.execute(
        select(DerivedMetric).where(
            DerivedMetric.company_id == company.id,
            DerivedMetric.metric_name == metric_name,
            DerivedMetric.as_of_date == as_of_date,
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = DerivedMetric(
            company_id=company.id, metric_name=metric_name, as_of_date=as_of_date
        )
        session.add(existing)
    existing.value = value
    existing.computed_at = datetime.utcnow()
    session.flush()


def get_derived_metrics(session: Session, ticker: str) -> dict:
    company = get_company_by_ticker(session, ticker)
    if company is None:
        return {}
    rows = session.execute(
        select(DerivedMetric)
        .where(DerivedMetric.company_id == company.id)
        .order_by(DerivedMetric.as_of_date.desc())
    ).scalars()
    latest: dict = {}
    for row in rows:
        latest.setdefault(row.metric_name, row.value)
    return latest


def record_quality_score(
    session: Session,
    company: Company,
    run_id: str,
    dataset_name: str,
    scores: dict,
) -> DataQualityScore:
    record = DataQualityScore(
        company_id=company.id,
        run_id=run_id,
        dataset_name=dataset_name,
        completeness_score=scores["completeness"],
        freshness_score=scores["freshness"],
        outlier_score=scores["outlier"],
        reconciliation_score=scores["reconciliation"],
        composite_score=scores["composite"],
        details_json=scores.get("details", {}),
    )
    session.add(record)
    session.flush()
    return record


def get_latest_quality_scores(session: Session, ticker: str) -> dict:
    company = get_company_by_ticker(session, ticker)
    if company is None:
        return {}
    rows = session.execute(
        select(DataQualityScore)
        .where(DataQualityScore.company_id == company.id)
        .order_by(DataQualityScore.computed_at.desc())
    ).scalars()
    latest: dict = {}
    for row in rows:
        latest.setdefault(row.dataset_name, row)
    return latest


def log_pipeline_stage(
    session: Session,
    run_id: str,
    ticker: str,
    stage: str,
    status: str,
    rows_processed: int = 0,
    error_message: Optional[str] = None,
) -> PipelineRunLog:
    record = PipelineRunLog(
        run_id=run_id,
        ticker=ticker.upper(),
        stage=stage,
        status=status,
        finished_at=datetime.utcnow() if status in ("success", "failed", "skipped") else None,
        rows_processed=rows_processed,
        error_message=error_message,
    )
    session.add(record)
    session.flush()
    return record


def get_run_log(session: Session, run_id: str) -> list[PipelineRunLog]:
    return list(
        session.execute(
            select(PipelineRunLog)
            .where(PipelineRunLog.run_id == run_id)
            .order_by(PipelineRunLog.started_at)
        ).scalars()
    )


def count_rows(session: Session, model) -> int:
    return len(list(session.execute(select(model)).scalars()))
