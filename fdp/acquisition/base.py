"""Abstract acquisition interface.

Every market-data source (a paid vendor, a free API, a bundled fixture file)
implements this same contract, so the rest of the platform (validation,
modeling, the ETL pipeline) never needs to know where the data came from --
it just calls `AbstractMarketDataClient` methods and reads `source_name` for
provenance/reconciliation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from fdp.acquisition.schemas import (
    RawCashFlowRow,
    RawCompanyProfile,
    RawIncomeStatementRow,
    RawPriceBar,
)


class AbstractMarketDataClient(ABC):
    #: short, stable identifier stored as `source` on every row this client
    #: produces -- used for provenance and cross-source reconciliation.
    source_name: str

    @abstractmethod
    def get_company_profile(self, ticker: str) -> RawCompanyProfile:
        """Return basic descriptive metadata for a ticker."""

    @abstractmethod
    def get_prices(self, ticker: str, lookback_days: int = 400) -> List[RawPriceBar]:
        """Return daily OHLCV bars, oldest first, covering at least `lookback_days`."""

    @abstractmethod
    def get_income_statements(
        self, ticker: str, limit: int = 6
    ) -> List[RawIncomeStatementRow]:
        """Return up to `limit` most recent annual income-statement periods."""

    @abstractmethod
    def get_cash_flows(self, ticker: str, limit: int = 6) -> List[RawCashFlowRow]:
        """Return up to `limit` most recent annual cash-flow-statement periods."""
