from datetime import date

from fdp.quality.checks import completeness_score, freshness_score, outlier_score, reconciliation_score


def test_completeness_score():
    assert completeness_score(8, 10) == 0.8
    assert completeness_score(0, 0) == 0.0
    assert completeness_score(5, 5) == 1.0


def test_freshness_score_full_when_recent():
    assert freshness_score(date(2024, 1, 1), date(2024, 1, 2), fresh_days=3, stale_days=30) == 1.0


def test_freshness_score_zero_when_very_stale():
    assert freshness_score(date(2024, 1, 1), date(2024, 3, 1), fresh_days=3, stale_days=30) == 0.0


def test_freshness_score_interpolates():
    # halfway between fresh_days=0 and stale_days=10 -> age=5 -> score ~0.5
    score = freshness_score(date(2024, 1, 1), date(2024, 1, 6), fresh_days=0, stale_days=10)
    assert 0.4 < score < 0.6


def test_freshness_score_none_date():
    assert freshness_score(None, date(2024, 1, 1), fresh_days=3, stale_days=30) == 0.0


def test_outlier_score_flags_injected_outlier():
    values = [0.01, 0.012, 0.009, 0.011, 0.013, 0.5, 0.010, 0.0095]  # 0.5 is a clear outlier
    score, flagged = outlier_score(values)
    assert 5 in flagged
    assert score < 1.0


def test_outlier_score_clean_series():
    values = [0.01, 0.011, 0.009, 0.0105, 0.0095, 0.0102]
    score, flagged = outlier_score(values)
    assert score == 1.0
    assert flagged == []


def test_outlier_score_too_few_points():
    score, flagged = outlier_score([0.01, 0.02])
    assert score == 1.0
    assert flagged == []


def test_reconciliation_no_secondary_source():
    score, evaluated = reconciliation_score({"a": 1.0}, None)
    assert score == 1.0
    assert evaluated is False


def test_reconciliation_agreement():
    score, evaluated = reconciliation_score({"a": 100.0}, {"a": 100.1}, tolerance=0.02)
    assert evaluated is True
    assert score > 0.9


def test_reconciliation_disagreement():
    score, evaluated = reconciliation_score({"a": 100.0}, {"a": 150.0}, tolerance=0.02)
    assert evaluated is True
    assert score < 0.5
