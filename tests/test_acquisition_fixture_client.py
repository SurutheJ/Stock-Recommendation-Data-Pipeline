def test_get_company_profile(fixture_client):
    profile = fixture_client.get_company_profile("AAPL")
    assert profile.ticker == "AAPL"
    assert profile.name


def test_get_prices_non_empty(fixture_client):
    bars = fixture_client.get_prices("AAPL")
    assert len(bars) > 0
    assert bars[0].date


def test_get_income_statements(fixture_client):
    rows = fixture_client.get_income_statements("AAPL")
    assert len(rows) == 4


def test_get_cash_flows(fixture_client):
    rows = fixture_client.get_cash_flows("MSFT")
    assert len(rows) == 4


def test_unknown_ticker_raises(fixture_client):
    from fdp.acquisition.fixture_client import FixtureNotFoundError

    import pytest

    with pytest.raises(FixtureNotFoundError):
        fixture_client.get_company_profile("NOPE")
