"""The relational data model.

`Company` is the root entity; `PriceObservation`, `IncomeStatementPeriod`, and
`CashFlowPeriod` are the raw modeled datasets acquired from a source.
`DerivedMetric` is the deliberate *interconnection point*: every row it holds
(a YoY growth rate, a moving average, a P/E ratio) is computed by joining
price data with fundamentals data for the same company, which is what lets
the recommendation engine reason across datasets instead of within just one.

`DataQualityScore` and `PipelineRunLog` are the audit trail: every pipeline
run is logged stage-by-stage, and every dataset it touches gets a scored,
timestamped quality record tied back to that run.
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), default="Unknown")
    sector: Mapped[str] = mapped_column(String(100), default="Unknown")
    industry: Mapped[str] = mapped_column(String(100), default="Unknown")
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    prices: Mapped[list["PriceObservation"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    income_statements: Mapped[list["IncomeStatementPeriod"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    cash_flows: Mapped[list["CashFlowPeriod"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    derived_metrics: Mapped[list["DerivedMetric"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    quality_scores: Mapped[list["DataQualityScore"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )


class PriceObservation(Base):
    __tablename__ = "price_observations"
    __table_args__ = (UniqueConstraint("company_id", "date", name="uq_price_company_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    date: Mapped[date_type] = mapped_column(Date, index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    adj_close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(32))
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship(back_populates="prices")


class IncomeStatementPeriod(Base):
    __tablename__ = "income_statement_periods"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "period_end_date", "period_type", name="uq_income_company_period"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    period_end_date: Mapped[date_type] = mapped_column(Date, index=True)
    period_type: Mapped[str] = mapped_column(String(2))
    fiscal_year: Mapped[int] = mapped_column(Integer)
    revenue: Mapped[float] = mapped_column(Float)
    net_income: Mapped[float] = mapped_column(Float)
    eps_diluted: Mapped[float] = mapped_column(Float)
    operating_income: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(32))
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship(back_populates="income_statements")


class CashFlowPeriod(Base):
    __tablename__ = "cash_flow_periods"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "period_end_date", "period_type", name="uq_cashflow_company_period"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    period_end_date: Mapped[date_type] = mapped_column(Date, index=True)
    period_type: Mapped[str] = mapped_column(String(2))
    fiscal_year: Mapped[int] = mapped_column(Integer)
    operating_cash_flow: Mapped[float] = mapped_column(Float)
    capital_expenditures: Mapped[float] = mapped_column(Float)
    free_cash_flow: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(32))
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship(back_populates="cash_flows")


class DerivedMetric(Base):
    """A metric computed by joining >=1 raw dataset, keyed so it can be
    upserted idempotently. This table is what makes the platform's datasets
    *interconnected* rather than siloed per source."""

    __tablename__ = "derived_metrics"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "metric_name", "as_of_date", name="uq_derived_company_metric_date"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    metric_name: Mapped[str] = mapped_column(String(64), index=True)
    as_of_date: Mapped[date_type] = mapped_column(Date, index=True)
    value: Mapped[float] = mapped_column(Float)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship(back_populates="derived_metrics")


class DataQualityScore(Base):
    __tablename__ = "data_quality_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    run_id: Mapped[str] = mapped_column(String(36), index=True)
    dataset_name: Mapped[str] = mapped_column(String(32))
    completeness_score: Mapped[float] = mapped_column(Float)
    freshness_score: Mapped[float] = mapped_column(Float)
    outlier_score: Mapped[float] = mapped_column(Float)
    reconciliation_score: Mapped[float] = mapped_column(Float)
    composite_score: Mapped[float] = mapped_column(Float)
    details_json: Mapped[dict] = mapped_column(JSON, default=dict)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship(back_populates="quality_scores")


class PipelineRunLog(Base):
    """One row per pipeline stage transition -- the audit trail that lets
    process-quality issues be diagnosed after the fact."""

    __tablename__ = "pipeline_run_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), index=True)
    ticker: Mapped[str] = mapped_column(String(16))
    stage: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rows_processed: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
