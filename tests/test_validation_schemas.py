from fdp.acquisition.schemas import RawIncomeStatementRow, RawPriceBar
from fdp.validation.models import validate_income_statements, validate_price_bars


def _bar(**overrides):
    base = dict(date="2024-01-02", open=100.0, high=101.0, low=99.0, close=100.5, adj_close=100.5, volume=1000)
    base.update(overrides)
    return RawPriceBar.model_validate(base)


def test_valid_price_bar_passes():
    valid, rejected = validate_price_bars([_bar()])
    assert len(valid) == 1
    assert len(rejected) == 0


def test_negative_price_rejected():
    valid, rejected = validate_price_bars([_bar(close=-5.0)])
    assert len(valid) == 0
    assert len(rejected) == 1


def test_high_less_than_low_rejected():
    valid, rejected = validate_price_bars([_bar(high=90.0, low=99.0)])
    assert len(valid) == 0
    assert len(rejected) == 1


def test_negative_volume_rejected():
    valid, rejected = validate_price_bars([_bar(volume=-10)])
    assert len(valid) == 0
    assert len(rejected) == 1


def test_missing_close_rejected():
    valid, rejected = validate_price_bars([_bar(close=None)])
    assert len(valid) == 0
    assert len(rejected) == 1


def test_negative_revenue_rejected():
    row = RawIncomeStatementRow(
        period_end_date="2024-09-30", period_type="FY", fiscal_year=2024,
        revenue=-100.0, net_income=10.0, eps_diluted=1.0, operating_income=5.0,
    )
    valid, rejected = validate_income_statements([row])
    assert len(valid) == 0
    assert len(rejected) == 1


def test_missing_eps_rejected():
    row = RawIncomeStatementRow(
        period_end_date="2024-09-30", period_type="FY", fiscal_year=2024,
        revenue=100.0, net_income=10.0, eps_diluted=None, operating_income=5.0,
    )
    valid, rejected = validate_income_statements([row])
    assert len(valid) == 0
    assert len(rejected) == 1
