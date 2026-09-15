"""One-shot demo: ingest every bundled fixture ticker and print a summary of
each one's data-quality scorecard and recommendation.

    python scripts/seed_demo.py
"""

from __future__ import annotations

from fdp.acquisition.fixture_client import FixtureClient
from fdp.config import FIXTURES_DIR
from fdp.modeling.database import build_default_session_factory
from fdp.pipeline.etl import run_pipeline

TICKERS = sorted({p.name.split("_")[0] for p in FIXTURES_DIR.glob("*_profile.json")})


def main() -> None:
    session_factory = build_default_session_factory()
    client = FixtureClient()

    for ticker in TICKERS:
        result = run_pipeline(ticker, client, session_factory)
        print(f"\n=== {ticker} ===")
        print(f"rows loaded: {result.rows_processed}  rejected: {result.rejected_counts}")
        for dataset, scores in result.quality_scores.items():
            print(f"  {dataset:16s} composite={scores['composite']:.2f}")
        print(f"  -> {result.recommendation.reasoning}")


if __name__ == "__main__":
    main()
