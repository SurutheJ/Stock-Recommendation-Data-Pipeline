from datetime import date

from fdp.validation.business_rules import check_income_statements, check_prices
from fdp.validation.models import ValidatedIncomeStatementRow, ValidatedPriceBar


def _income_row(fiscal_year, period_end_date):
    return ValidatedIncomeStatementRow(
        period_end_date=period_end_date, period_type="FY", fiscal_year=fiscal_year,
        revenue=100.0, net_income=10.0, eps_diluted=1.0, operating_income=5.0,
    )


def test_duplicate_periods_flagged():
    rows = [_income_row(2023, "2023-09-30"), _income_row(2023, "2023-09-30")]
    report = check_income_statements(rows)
    assert any("duplicate" in w for w in report.warnings)


def test_out_of_order_periods_flagged():
    rows = [_income_row(2024, "2024-09-30"), _income_row(2023, "2023-09-30")]
    report = check_income_statements(rows)
    assert any("chronological" in w for w in report.warnings)


def test_clean_prices_no_warnings():
    bars = [
        ValidatedPriceBar(
            date=date(2024, 1, 1), open=100, high=101, low=99, close=100, adj_close=100, volume=1000
        ),
        ValidatedPriceBar(
            date=date(2024, 1, 2), open=100, high=102, low=99, close=101, adj_close=101, volume=1100
        ),
    ]
    report = check_prices(bars)
    assert report.warnings == []
