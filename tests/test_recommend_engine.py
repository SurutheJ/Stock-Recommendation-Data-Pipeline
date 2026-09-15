from fdp.recommend.engine import generate_recommendation

STRONG_GROWTH_EXPENSIVE_METRICS = {
    "latest_close": 220.0,
    "sma_50": 200.0,
    "sma_200": 190.0,
    "pe_ratio": 55.0,  # expensive
    "revenue_yoy_growth": 0.35,
    "net_income_yoy_growth": 0.30,
    "eps_yoy_growth": 0.40,
    "fcf_yoy_growth": 0.30,
}

CHEAP_LOW_GROWTH_METRICS = {
    "latest_close": 100.0,
    "sma_50": 100.0,
    "sma_200": 100.0,
    "pe_ratio": 8.0,  # cheap
    "revenue_yoy_growth": 0.01,
    "net_income_yoy_growth": 0.0,
    "eps_yoy_growth": 0.0,
    "fcf_yoy_growth": 0.01,
}


def test_growth_investor_favors_high_growth_expensive_stock():
    rec = generate_recommendation("GROWCO", STRONG_GROWTH_EXPENSIVE_METRICS, data_trust_score=0.9, profile_name="growth_investor")
    assert rec.verdict == "BUY"


def test_value_investor_penalizes_expensive_stock():
    rec_growth_co = generate_recommendation(
        "GROWCO", STRONG_GROWTH_EXPENSIVE_METRICS, data_trust_score=0.9, profile_name="value_investor"
    )
    rec_cheap_co = generate_recommendation(
        "CHEAPCO", CHEAP_LOW_GROWTH_METRICS, data_trust_score=0.9, profile_name="value_investor"
    )
    # the expensive high-growth stock should score lower under a value lens
    # than it does under a growth lens -- valuation drags it down
    assert rec_growth_co.weighted_score < generate_recommendation(
        "GROWCO", STRONG_GROWTH_EXPENSIVE_METRICS, data_trust_score=0.9, profile_name="growth_investor"
    ).weighted_score


def test_quality_investor_caps_buy_when_data_trust_low():
    rec_trusted = generate_recommendation(
        "GROWCO", STRONG_GROWTH_EXPENSIVE_METRICS, data_trust_score=0.9, profile_name="quality_investor"
    )
    rec_untrusted = generate_recommendation(
        "GROWCO", STRONG_GROWTH_EXPENSIVE_METRICS, data_trust_score=0.3, profile_name="quality_investor"
    )
    assert rec_trusted.verdict == "BUY"
    assert rec_untrusted.verdict == "HOLD"
    assert rec_untrusted.trust_adjusted is True


def test_balanced_profile_reasoning_mentions_trust_score():
    rec = generate_recommendation("GROWCO", STRONG_GROWTH_EXPENSIVE_METRICS, data_trust_score=0.42, profile_name="balanced")
    assert "Data Trust Score 0.42" in rec.reasoning
