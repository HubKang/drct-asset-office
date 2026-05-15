from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def _assert_guardrailed_evidence_package(data: dict) -> None:
    assert data["stock"]["stock_id"] > 0
    assert data["price_summary"]["source"] == "pykrx"
    assert data["price_summary"]["latest_trade_date"]
    assert data["price_summary"]["latest_close_price"] is not None
    assert "trading_value" not in data["price_summary"]
    assert "instruction_guardrails" in data
    assert len(data["instruction_guardrails"]) >= 2
    assert "data_quality_notes" in data
    assert all(key not in data for key in ("final_opinion", "target_price", "action"))
    guardrails_text = " ".join(data["instruction_guardrails"])
    assert "자동 매수" in guardrails_text
    assert "목표가" in guardrails_text


def test_advisory_evidence_package_for_dongwha() -> None:
    response = client.get("/advisory/evidence-package/10010")
    assert response.status_code == 200
    data = response.json()
    _assert_guardrailed_evidence_package(data)
    assert data["stock"]["stock_id"] == 10010
    assert data["market_metrics_summary"] is not None
    assert data["market_metrics_summary"]["source"] == "marcap"
    assert data["market_metrics_summary"]["staleness_level"] == "severely_stale"
    assert data["market_metrics_summary"]["trading_value"] is not None


def test_advisory_evidence_package_for_dosan_robotics() -> None:
    response = client.get("/advisory/evidence-package/10803")
    assert response.status_code == 200
    data = response.json()
    _assert_guardrailed_evidence_package(data)
    assert data["stock"]["stock_id"] == 10803
    assert data["market_metrics_summary"] is not None
    assert data["market_metrics_summary"]["source"] == "marcap"
    assert data["market_metrics_summary"]["staleness_level"] == "severely_stale"


def test_advisory_evidence_package_returns_404_for_missing_stock() -> None:
    response = client.get("/advisory/evidence-package/99999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "stock not found"
