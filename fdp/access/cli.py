"""Command-line access to the platform: ingest a ticker, inspect its data
quality, get a profile-weighted recommendation, or start the API server.
"""

from __future__ import annotations

import sys

import click

from fdp.config import DEFAULT_DB_URL, INVESTOR_PROFILES
from fdp.modeling.database import build_default_session_factory
from fdp.modeling import repository as repo
from fdp.quality.scoring import trust_label


def _get_client(mode: str):
    if mode == "fixture":
        from fdp.acquisition.fixture_client import FixtureClient

        return FixtureClient()
    from fdp.acquisition.yfinance_client import YFinanceClient

    return YFinanceClient()


@click.group()
def cli():
    """Trade Signal Platform -- data-management-grade stock recommendations."""


@cli.command()
@click.option("--ticker", required=True, help="Ticker symbol, e.g. AAPL")
@click.option(
    "--mode",
    type=click.Choice(["fixture", "live"]),
    default="fixture",
    show_default=True,
    help="fixture = bundled offline sample data (no key/network); live = free yfinance feed",
)
@click.option("--db-url", default=DEFAULT_DB_URL, show_default=True)
def ingest(ticker: str, mode: str, db_url: str):
    """Run the full ETL pipeline for TICKER: acquire, validate, load, derive, score, recommend."""
    from fdp.pipeline.etl import PipelineError, run_pipeline

    session_factory = build_default_session_factory(db_url)
    client = _get_client(mode)
    try:
        result = run_pipeline(ticker, client, session_factory)
    except PipelineError as exc:
        click.secho(f"Pipeline failed: {exc}", fg="red")
        sys.exit(1)

    click.secho(f"\n=== Ingested {result.ticker} (run {result.run_id[:8]}) ===", bold=True)
    click.echo(f"Rows loaded: {result.rows_processed}")
    if any(result.rejected_counts.values()):
        click.secho(f"Rows rejected by validation: {result.rejected_counts}", fg="yellow")
    for dataset, warnings in result.warnings.items():
        for w in warnings:
            click.secho(f"  [warning] {w}", fg="yellow")

    click.secho("\nData Quality:", bold=True)
    for dataset, scores in result.quality_scores.items():
        click.echo(
            f"  {dataset:16s} composite={scores['composite']:.2f} "
            f"(completeness={scores['completeness']:.2f} freshness={scores['freshness']:.2f} "
            f"outlier={scores['outlier']:.2f} reconciliation={scores['reconciliation']:.2f})"
        )

    rec = result.recommendation
    click.secho(f"\nRecommendation ({rec.profile_label}):", bold=True)
    click.echo(f"  {rec.reasoning}")


@cli.command("quality-report")
@click.option("--ticker", required=True)
@click.option("--db-url", default=DEFAULT_DB_URL, show_default=True)
def quality_report(ticker: str, db_url: str):
    """Show the latest data-quality scorecard for TICKER (run `ingest` first)."""
    session_factory = build_default_session_factory(db_url)
    with session_factory() as session:
        scores = repo.get_latest_quality_scores(session, ticker)
    if not scores:
        click.secho(f"No data for {ticker.upper()} -- run `fdp ingest --ticker {ticker}` first.", fg="red")
        sys.exit(1)

    click.secho(f"Data Quality Scorecard: {ticker.upper()}", bold=True)
    for dataset, record in scores.items():
        click.echo(
            f"  {dataset:16s} composite={record.composite_score:.2f} "
            f"({trust_label(record.composite_score)}) -- completeness={record.completeness_score:.2f} "
            f"freshness={record.freshness_score:.2f} outlier={record.outlier_score:.2f} "
            f"reconciliation={record.reconciliation_score:.2f}"
        )


@cli.command()
@click.option("--ticker", required=True)
@click.option(
    "--profile",
    type=click.Choice(list(INVESTOR_PROFILES)),
    default="balanced",
    show_default=True,
)
@click.option("--db-url", default=DEFAULT_DB_URL, show_default=True)
def recommend(ticker: str, profile: str, db_url: str):
    """Get a Buy/Hold/Sell recommendation for TICKER under a customer PROFILE
    (run `ingest` first so the underlying data exists)."""
    import statistics

    from fdp.recommend.engine import generate_recommendation

    session_factory = build_default_session_factory(db_url)
    with session_factory() as session:
        metrics = repo.get_derived_metrics(session, ticker)
        quality = repo.get_latest_quality_scores(session, ticker)
    if not metrics or not quality:
        click.secho(f"No data for {ticker.upper()} -- run `fdp ingest --ticker {ticker}` first.", fg="red")
        sys.exit(1)

    data_trust_score = statistics.fmean(r.composite_score for r in quality.values())
    rec = generate_recommendation(ticker.upper(), metrics, data_trust_score, profile)
    click.secho(f"{rec.ticker} -- {rec.profile_label}", bold=True)
    click.echo(f"  {rec.reasoning}")
    click.echo(f"  weighted_score={rec.weighted_score:.3f}")


@cli.command()
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8000, show_default=True)
@click.option("--db-url", default=DEFAULT_DB_URL, show_default=True)
def serve(host: str, port: int, db_url: str):
    """Start the FastAPI server exposing modeled data as queryable endpoints."""
    import uvicorn

    from fdp.access.api import create_app

    session_factory = build_default_session_factory(db_url)
    app = create_app(session_factory)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    cli()
