"""Free, no-API-key live acquisition client backed by `yfinance`.

This is the "real world" counterpart to the fixture client, implementing the
exact same `AbstractMarketDataClient` contract. It is intentionally kept
optional at runtime (only imported when `--mode live` is actually used) so
the rest of the platform, including the full test suite, never depends on
network access.
"""

from __future__ import annotations

from typing import List

from fdp.acquisition.base import AbstractMarketDataClient
from fdp.acquisition.schemas import (
    RawCashFlowRow,
    RawCompanyProfile,
    RawIncomeStatementRow,
    RawPriceBar,
)


class YFinanceClient(AbstractMarketDataClient):
    source_name = "yfinance"

    def __init__(self):
        try:
            import yfinance  # noqa: F401
        except ImportError as exc:  # pragma: no cover - exercised only in live mode
            raise RuntimeError(
                "yfinance is required for --mode live (pip install yfinance)"
            ) from exc

    def _ticker(self, ticker: str):
        import yfinance as yf

        return yf.Ticker(ticker)

    def get_company_profile(self, ticker: str) -> RawCompanyProfile:
        info = self._ticker(ticker).info or {}
        return RawCompanyProfile(
            ticker=ticker.upper(),
            name=info.get("shortName") or info.get("longName"),
            sector=info.get("sector"),
            industry=info.get("industry"),
            currency=info.get("currency"),
        )

    def get_prices(self, ticker: str, lookback_days: int = 400) -> List[RawPriceBar]:
        history = self._ticker(ticker).history(period="2y", interval="1d")
        bars: List[RawPriceBar] = []
        for idx, row in history.iterrows():
            bars.append(
                RawPriceBar(
                    date=idx.strftime("%Y-%m-%d"),
                    open=_safe_float(row.get("Open")),
                    high=_safe_float(row.get("High")),
                    low=_safe_float(row.get("Low")),
                    close=_safe_float(row.get("Close")),
                    adj_close=_safe_float(row.get("Close")),
                    volume=_safe_float(row.get("Volume")),
                )
            )
        return bars[-lookback_days:] if lookback_days else bars

    def get_income_statements(
        self, ticker: str, limit: int = 6
    ) -> List[RawIncomeStatementRow]:
        stmt = self._ticker(ticker).income_stmt
        rows: List[RawIncomeStatementRow] = []
        if stmt is None or stmt.empty:
            return rows
        for period_end in stmt.columns:
            col = stmt[period_end]
            rows.append(
                RawIncomeStatementRow(
                    period_end_date=period_end.strftime("%Y-%m-%d"),
                    period_type="FY",
                    fiscal_year=period_end.year,
                    revenue=_safe_lookup(col, "Total Revenue"),
                    net_income=_safe_lookup(col, "Net Income"),
                    eps_diluted=_safe_lookup(col, "Diluted EPS"),
                    operating_income=_safe_lookup(col, "Operating Income"),
                )
            )
        rows.sort(key=lambda r: r.period_end_date)
        return rows[-limit:] if limit else rows

    def get_cash_flows(self, ticker: str, limit: int = 6) -> List[RawCashFlowRow]:
        stmt = self._ticker(ticker).cash_flow
        rows: List[RawCashFlowRow] = []
        if stmt is None or stmt.empty:
            return rows
        for period_end in stmt.columns:
            col = stmt[period_end]
            capex = _safe_lookup(col, "Capital Expenditure")
            rows.append(
                RawCashFlowRow(
                    period_end_date=period_end.strftime("%Y-%m-%d"),
                    period_type="FY",
                    fiscal_year=period_end.year,
                    operating_cash_flow=_safe_lookup(col, "Operating Cash Flow"),
                    capital_expenditures=abs(capex) if capex is not None else None,
                )
            )
        rows.sort(key=lambda r: r.period_end_date)
        return rows[-limit:] if limit else rows


def _safe_float(value) -> float | None:
    try:
        if value is None:
            return None
        f = float(value)
        return f if f == f else None  # filter NaN
    except (TypeError, ValueError):
        return None


def _safe_lookup(series, label: str) -> float | None:
    try:
        return _safe_float(series.get(label))
    except Exception:
        return None
