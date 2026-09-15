import pytest
from fastapi.testclient import TestClient

from fdp.access.api import create_app
from fdp.pipeline.etl import run_pipeline


@pytest.fixture()
def client(session_factory, fixture_client):
    run_pipeline("AAPL", fixture_client, session_factory)
    app = create_app(session_factory)
    return TestClient(app)


def test_list_companies(client):
    resp = client.get("/companies")
    assert resp.status_code == 200
    tickers = [c["ticker"] for c in resp.json()]
    assert "AAPL" in tickers


def test_get_prices(client):
    resp = client.get("/companies/AAPL/prices")
    assert resp.status_code == 200
    assert len(resp.json()) > 0


def test_get_fundamentals(client):
    resp = client.get("/companies/AAPL/fundamentals")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["income_statements"]) == 4
    assert len(body["cash_flows"]) == 4


def test_get_quality(client):
    resp = client.get("/companies/AAPL/quality")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"prices", "income_statement", "cash_flow"}


def test_get_recommendation(client):
    resp = client.get("/companies/AAPL/recommendation", params={"profile": "growth_investor"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["verdict"] in {"BUY", "HOLD", "SELL"}
    assert body["profile"] == "growth_investor"


def test_unknown_ticker_404(client):
    resp = client.get("/companies/NOPE/prices")
    assert resp.status_code == 404
