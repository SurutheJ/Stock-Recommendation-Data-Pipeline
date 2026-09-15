"""Raw, loosely-typed payload shapes as they arrive from an acquisition client.

These deliberately accept missing/incomplete data (everything but the natural
key is Optional) because real upstream feeds are messy -- rejecting bad rows
is the validation layer's job (`fdp.validation`), not the acquisition layer's.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class RawCompanyProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ticker: str
    name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    currency: Optional[str] = None


class RawPriceBar(BaseModel):
    model_config = ConfigDict(extra="ignore")

    date: str
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    adj_close: Optional[float] = None
    volume: Optional[float] = None


class RawIncomeStatementRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    period_end_date: str
    period_type: str = "FY"
    fiscal_year: Optional[int] = None
    revenue: Optional[float] = None
    net_income: Optional[float] = None
    eps_diluted: Optional[float] = None
    operating_income: Optional[float] = None


class RawCashFlowRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    period_end_date: str
    period_type: str = "FY"
    fiscal_year: Optional[int] = None
    operating_cash_flow: Optional[float] = None
    capital_expenditures: Optional[float] = None
