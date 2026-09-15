"""Validated, strictly-typed models plus the functions that turn a batch of
raw acquisition rows into (valid_rows, rejected_rows) -- the schema-level
half of the platform's data-validation story.

Rows that fail here are never loaded into the data model at all; they are
counted as "incomplete" for the data-quality completeness score instead.
"""

from __future__ import annotations

from datetime import date as date_type
from typing import Iterable, List, Literal, Optional, Tuple

from pydantic import BaseModel, field_validator, model_validator

from fdp.acquisition.schemas import (
    RawCashFlowRow,
    RawCompanyProfile,
    RawIncomeStatementRow,
    RawPriceBar,
)


class Rejection(BaseModel):
    raw: dict
    reason: str


class ValidatedCompanyProfile(BaseModel):
    ticker: str
    name: str = "Unknown"
    sector: str = "Unknown"
    industry: str = "Unknown"
    currency: str = "USD"

    @field_validator("ticker")
    @classmethod
    def _ticker_not_blank(cls, v: str) -> str:
        v = (v or "").strip().upper()
        if not v:
            raise ValueError("ticker must not be blank")
        return v


class ValidatedPriceBar(BaseModel):
    date: date_type
    open: float
    high: float
    low: float
    close: float
    adj_close: float
    volume: int

    @field_validator("open", "high", "low", "close", "adj_close")
    @classmethod
    def _positive_price(cls, v: float) -> float:
        if v is None or v <= 0:
            raise ValueError("prices must be positive")
        return v

    @field_validator("volume")
    @classmethod
    def _non_negative_volume(cls, v: int) -> int:
        if v is None or v < 0:
            raise ValueError("volume must be non-negative")
        return v

    @model_validator(mode="after")
    def _high_low_consistent(self) -> "ValidatedPriceBar":
        if self.high < self.low:
            raise ValueError("high must be >= low")
        return self


class ValidatedIncomeStatementRow(BaseModel):
    period_end_date: date_type
    period_type: Literal["FY", "Q"] = "FY"
    fiscal_year: int
    revenue: float
    net_income: float
    eps_diluted: float
    operating_income: float

    @field_validator("revenue")
    @classmethod
    def _revenue_non_negative(cls, v: float) -> float:
        if v is None or v < 0:
            raise ValueError("revenue cannot be negative")
        return v


class ValidatedCashFlowRow(BaseModel):
    period_end_date: date_type
    period_type: Literal["FY", "Q"] = "FY"
    fiscal_year: int
    operating_cash_flow: float
    capital_expenditures: float

    @property
    def free_cash_flow(self) -> float:
        return self.operating_cash_flow - abs(self.capital_expenditures)


def validate_price_bars(
    raw_bars: Iterable[RawPriceBar],
) -> Tuple[List[ValidatedPriceBar], List[Rejection]]:
    valid: List[ValidatedPriceBar] = []
    rejected: List[Rejection] = []
    for raw in raw_bars:
        try:
            valid.append(ValidatedPriceBar.model_validate(raw.model_dump()))
        except Exception as exc:  # pydantic ValidationError or our own ValueError
            rejected.append(Rejection(raw=raw.model_dump(), reason=str(exc)))
    return valid, rejected


def validate_income_statements(
    raw_rows: Iterable[RawIncomeStatementRow],
) -> Tuple[List[ValidatedIncomeStatementRow], List[Rejection]]:
    valid: List[ValidatedIncomeStatementRow] = []
    rejected: List[Rejection] = []
    for raw in raw_rows:
        try:
            valid.append(ValidatedIncomeStatementRow.model_validate(raw.model_dump()))
        except Exception as exc:
            rejected.append(Rejection(raw=raw.model_dump(), reason=str(exc)))
    return valid, rejected


def validate_cash_flows(
    raw_rows: Iterable[RawCashFlowRow],
) -> Tuple[List[ValidatedCashFlowRow], List[Rejection]]:
    valid: List[ValidatedCashFlowRow] = []
    rejected: List[Rejection] = []
    for raw in raw_rows:
        try:
            valid.append(ValidatedCashFlowRow.model_validate(raw.model_dump()))
        except Exception as exc:
            rejected.append(Rejection(raw=raw.model_dump(), reason=str(exc)))
    return valid, rejected


def validate_company_profile(raw: RawCompanyProfile) -> ValidatedCompanyProfile:
    data = {k: v for k, v in raw.model_dump().items() if v is not None}
    return ValidatedCompanyProfile.model_validate(data)
