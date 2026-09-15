"""Proves the ETL pipeline is idempotent: running it twice for the same
ticker must not duplicate any modeled row -- only the audit trail
(`PipelineRunLog`) should grow.
"""

from fdp.modeling.orm_models import (
    CashFlowPeriod,
    Company,
    DataQualityScore,
    DerivedMetric,
    IncomeStatementPeriod,
    PipelineRunLog,
    PriceObservation,
)
from fdp.modeling.repository import count_rows
from fdp.pipeline.etl import run_pipeline


def test_running_pipeline_twice_does_not_duplicate_rows(session_factory, fixture_client):
    run_pipeline("AAPL", fixture_client, session_factory)
    with session_factory() as session:
        counts_after_first = {
            "companies": count_rows(session, Company),
            "prices": count_rows(session, PriceObservation),
            "income": count_rows(session, IncomeStatementPeriod),
            "cash_flow": count_rows(session, CashFlowPeriod),
            "derived": count_rows(session, DerivedMetric),
        }
        run_logs_after_first = count_rows(session, PipelineRunLog)

    run_pipeline("AAPL", fixture_client, session_factory)
    with session_factory() as session:
        counts_after_second = {
            "companies": count_rows(session, Company),
            "prices": count_rows(session, PriceObservation),
            "income": count_rows(session, IncomeStatementPeriod),
            "cash_flow": count_rows(session, CashFlowPeriod),
            "derived": count_rows(session, DerivedMetric),
        }
        run_logs_after_second = count_rows(session, PipelineRunLog)

    assert counts_after_first == counts_after_second
    assert run_logs_after_second > run_logs_after_first


def test_pipeline_records_quality_scores_and_recommendation(session_factory, fixture_client):
    result = run_pipeline("AAPL", fixture_client, session_factory)
    assert set(result.quality_scores) == {"prices", "income_statement", "cash_flow"}
    assert result.recommendation is not None
    assert result.recommendation.verdict in {"BUY", "HOLD", "SELL"}

    with session_factory() as session:
        assert count_rows(session, DataQualityScore) == 3


def test_pipeline_catches_bad_data_in_badco(session_factory, fixture_client):
    result = run_pipeline("BADCO", fixture_client, session_factory)
    assert sum(result.rejected_counts.values()) > 0
    # BADCO's data quality should be meaningfully worse than a clean ticker's
    aapl_result = run_pipeline("AAPL", fixture_client, session_factory)
    badco_trust = sum(s["composite"] for s in result.quality_scores.values()) / 3
    aapl_trust = sum(s["composite"] for s in aapl_result.quality_scores.values()) / 3
    assert badco_trust < aapl_trust
