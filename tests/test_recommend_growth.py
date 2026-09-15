import pytest

from fdp.recommend.factors import normalize_growth_score, normalize_pe_score, normalize_price_vs_avg_score
from fdp.recommend.growth import growth_series, simple_moving_average, yoy_growth


def test_yoy_growth_basic():
    assert yoy_growth(120, 100) == 0.2


def test_yoy_growth_negative():
    assert yoy_growth(80, 100) == -0.2


def test_yoy_growth_zero_previous_guarded():
    assert yoy_growth(100, 0) is None


def test_yoy_growth_missing_value_guarded():
    assert yoy_growth(None, 100) is None
    assert yoy_growth(100, None) is None


def test_growth_series():
    series = growth_series([(2021, 100), (2022, 120), (2023, 150)])
    assert series[0] == (2022, 0.2)
    assert abs(series[1][1] - 0.25) < 1e-9


def test_simple_moving_average():
    assert simple_moving_average([1, 2, 3, 4, 5], 3) == 4.0


def test_simple_moving_average_insufficient_data():
    assert simple_moving_average([1, 2], 5) is None


def test_normalize_growth_score_bounds():
    assert normalize_growth_score(-0.5) == 0.0
    assert normalize_growth_score(0.5) == 1.0
    assert normalize_growth_score(None) == 0.5
    assert normalize_growth_score(0.0) == 0.5


def test_normalize_pe_score():
    assert normalize_pe_score(5.0) == 0.0
    assert normalize_pe_score(40.0) == 1.0
    assert normalize_pe_score(None) == 0.5


def test_normalize_price_vs_avg_score():
    assert normalize_price_vs_avg_score(90, 100) == 0.0
    assert normalize_price_vs_avg_score(110, 100) == 1.0
    assert normalize_price_vs_avg_score(100, 100) == pytest.approx(0.5)
