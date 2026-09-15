"""Generates the offline demo/test fixtures under data/fixtures/.

Run once (already committed, so this is for transparency/reproducibility,
not something you need to re-run): `python scripts/generate_fixtures.py`.

Produces two "clean" tickers (AAPL, MSFT) with plausible multi-year
fundamentals and ~2 years of daily prices, and one deliberately messy
ticker (BADCO) with missing fields, stale prices, and an injected price
outlier -- used to prove the data-quality engine actually catches bad data.
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "data" / "fixtures"


def _write(ticker: str, suffix: str, payload) -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIXTURES_DIR / f"{ticker}_{suffix}.json"
    path.write_text(json.dumps(payload, indent=2))
    print(f"wrote {path}")


def _profile(ticker: str, name: str, sector: str, industry: str) -> dict:
    return {"ticker": ticker, "name": name, "sector": sector, "industry": industry, "currency": "USD"}


def _generate_prices(
    seed: int,
    start_price: float,
    days: int,
    drift: float,
    volatility: float,
    end_date: date,
    stale_offset_days: int = 0,
    injected_outlier_index: int | None = None,
    missing_close_indices: tuple[int, ...] = (),
) -> list[dict]:
    rng = random.Random(seed)
    last_date = end_date - timedelta(days=stale_offset_days)
    # walk back `days` *trading* days (Mon-Fri) from last_date
    dates = []
    d = last_date
    while len(dates) < days:
        if d.weekday() < 5:
            dates.append(d)
        d -= timedelta(days=1)
    dates.reverse()

    bars = []
    price = start_price
    for i, d in enumerate(dates):
        change = drift + rng.gauss(0, volatility)
        price = max(1.0, price * (1 + change))
        if injected_outlier_index is not None and i == injected_outlier_index:
            price = price * 4.5  # deliberate anomalous spike
        open_ = price * (1 - rng.uniform(0, 0.004))
        high = price * (1 + rng.uniform(0, 0.006))
        low = price * (1 - rng.uniform(0, 0.006))
        close = price if i not in missing_close_indices else None
        volume = int(rng.uniform(2e7, 9e7))
        bars.append(
            {
                "date": d.isoformat(),
                "open": round(open_, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "close": round(close, 2) if close is not None else None,
                "adj_close": round(close, 2) if close is not None else None,
                "volume": volume,
            }
        )
    return bars


def build_clean_ticker(
    ticker: str,
    name: str,
    sector: str,
    industry: str,
    seed: int,
    start_price: float,
    base_revenue: float,
    base_net_income: float,
    base_eps: float,
    base_ocf: float,
    base_capex: float,
    growth_rate: float,
) -> None:
    _write(ticker, "profile", _profile(ticker, name, sector, industry))

    prices = _generate_prices(
        seed=seed, start_price=start_price, days=260, drift=0.0006, volatility=0.014,
        end_date=date.today(),
    )
    _write(ticker, "prices", prices)

    current_year = date.today().year
    income_rows = []
    cash_flow_rows = []
    for i, year in enumerate(range(current_year - 4, current_year)):
        factor = (1 + growth_rate) ** i
        revenue = round(base_revenue * factor, 1)
        net_income = round(base_net_income * factor, 1)
        eps = round(base_eps * factor, 2)
        operating_income = round(net_income * 1.25, 1)
        ocf = round(base_ocf * factor, 1)
        capex = round(base_capex * factor, 1)
        income_rows.append(
            {
                "period_end_date": f"{year}-09-30",
                "period_type": "FY",
                "fiscal_year": year,
                "revenue": revenue,
                "net_income": net_income,
                "eps_diluted": eps,
                "operating_income": operating_income,
            }
        )
        cash_flow_rows.append(
            {
                "period_end_date": f"{year}-09-30",
                "period_type": "FY",
                "fiscal_year": year,
                "operating_cash_flow": ocf,
                "capital_expenditures": capex,
            }
        )
    _write(ticker, "income_statement", income_rows)
    _write(ticker, "cash_flow", cash_flow_rows)


def build_badco() -> None:
    ticker = "BADCO"
    _write(ticker, "profile", _profile(ticker, "BadCo Holdings", "Unknown", "Unknown"))

    prices = _generate_prices(
        seed=999, start_price=42.0, days=90, drift=0.0002, volatility=0.02,
        end_date=date.today(),
        stale_offset_days=45,  # data hasn't been refreshed in 45 days -> low freshness score
        injected_outlier_index=60,  # one deliberate anomalous spike -> low outlier score
        missing_close_indices=(10, 25, 40, 55, 70),  # missing fields -> low completeness score
    )
    _write(ticker, "prices", prices)

    # Missing/incomplete fundamentals: one period has no EPS, one has no revenue at all.
    income_rows = [
        {
            "period_end_date": "2021-12-31",
            "period_type": "FY",
            "fiscal_year": 2021,
            "revenue": 500.0,
            "net_income": 10.0,
            "eps_diluted": 0.50,
            "operating_income": 15.0,
        },
        {
            "period_end_date": "2022-12-31",
            "period_type": "FY",
            "fiscal_year": 2022,
            "revenue": 480.0,
            "net_income": -5.0,
            "eps_diluted": None,  # missing -> rejected by validation -> completeness hit
            "operating_income": 2.0,
        },
        {
            "period_end_date": "2023-12-31",
            "period_type": "FY",
            "fiscal_year": 2023,
            "revenue": None,  # missing required field -> rejected
            "net_income": -40.0,
            "eps_diluted": -1.10,
            "operating_income": -30.0,
        },
        {
            "period_end_date": "2024-12-31",
            "period_type": "FY",
            "fiscal_year": 2024,
            "revenue": 410.0,
            "net_income": -60.0,
            "eps_diluted": -1.60,
            "operating_income": -45.0,
        },
    ]
    _write(ticker, "income_statement", income_rows)

    cash_flow_rows = [
        {
            "period_end_date": "2021-12-31",
            "period_type": "FY",
            "fiscal_year": 2021,
            "operating_cash_flow": 20.0,
            "capital_expenditures": 8.0,
        },
        {
            "period_end_date": "2022-12-31",
            "period_type": "FY",
            "fiscal_year": 2022,
            "operating_cash_flow": -5.0,
            "capital_expenditures": 6.0,
        },
        {
            "period_end_date": "2023-12-31",
            "period_type": "FY",
            "fiscal_year": 2023,
            "operating_cash_flow": None,  # missing -> rejected
            "capital_expenditures": 5.0,
        },
        {
            "period_end_date": "2024-12-31",
            "period_type": "FY",
            "fiscal_year": 2024,
            "operating_cash_flow": -30.0,
            "capital_expenditures": 4.0,
        },
    ]
    _write(ticker, "cash_flow", cash_flow_rows)


if __name__ == "__main__":
    build_clean_ticker(
        "AAPL", "Apple Inc.", "Technology", "Consumer Electronics",
        seed=1, start_price=170.0,
        base_revenue=365000, base_net_income=95000, base_eps=6.0,
        base_ocf=105000, base_capex=11000, growth_rate=0.05,
    )
    build_clean_ticker(
        "MSFT", "Microsoft Corporation", "Technology", "Software - Infrastructure",
        seed=2, start_price=330.0,
        base_revenue=205000, base_net_income=72000, base_eps=9.6,
        base_ocf=89000, base_capex=24000, growth_rate=0.11,
    )
    build_badco()
