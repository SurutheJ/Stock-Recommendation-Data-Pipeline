"""Offline acquisition client backed by bundled JSON fixtures.

This is what makes the whole platform runnable and testable with zero
network access and no API key: `data/fixtures/<TICKER>_*.json` files stand
in for a live vendor feed, including one deliberately messy ticker (BADCO)
used to demonstrate that the data-quality engine actually catches bad data.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from fdp.acquisition.base import AbstractMarketDataClient
from fdp.acquisition.schemas import (
    RawCashFlowRow,
    RawCompanyProfile,
    RawIncomeStatementRow,
    RawPriceBar,
)
from fdp.config import FIXTURES_DIR


class FixtureNotFoundError(FileNotFoundError):
    """Raised when no fixture file exists for a requested ticker/dataset."""


class FixtureClient(AbstractMarketDataClient):
    source_name = "fixture"

    def __init__(self, fixtures_dir: Path = FIXTURES_DIR):
        self.fixtures_dir = Path(fixtures_dir)

    def _load(self, ticker: str, suffix: str) -> object:
        path = self.fixtures_dir / f"{ticker.upper()}_{suffix}.json"
        if not path.exists():
            raise FixtureNotFoundError(
                f"No fixture file for ticker={ticker!r} dataset={suffix!r} at {path}"
            )
        with path.open() as fh:
            return json.load(fh)

    def get_company_profile(self, ticker: str) -> RawCompanyProfile:
        payload = self._load(ticker, "profile")
        return RawCompanyProfile.model_validate(payload)

    def get_prices(self, ticker: str, lookback_days: int = 400) -> List[RawPriceBar]:
        payload = self._load(ticker, "prices")
        bars = [RawPriceBar.model_validate(row) for row in payload]
        return bars[-lookback_days:] if lookback_days else bars

    def get_income_statements(
        self, ticker: str, limit: int = 6
    ) -> List[RawIncomeStatementRow]:
        payload = self._load(ticker, "income_statement")
        rows = [RawIncomeStatementRow.model_validate(row) for row in payload]
        return rows[-limit:] if limit else rows

    def get_cash_flows(self, ticker: str, limit: int = 6) -> List[RawCashFlowRow]:
        payload = self._load(ticker, "cash_flow")
        rows = [RawCashFlowRow.model_validate(row) for row in payload]
        return rows[-limit:] if limit else rows
