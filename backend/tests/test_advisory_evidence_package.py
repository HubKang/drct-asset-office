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
    assert "news_summary_block" in data
    assert "disclosure_summary_block" in data
    assert "risk_summary_block" in data
    assert "recent_event_timeline" in data
    assert "technical_indicators_block" in data
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


def test_advisory_evidence_package_excludes_news_disclosure_blocks() -> None:
    response = client.get("/advisory/evidence-package/10010?include_news_disclosures_risk=false")
    assert response.status_code == 200
    data = response.json()
    assert data["news_summary_block"]["included"] is False
    assert data["disclosure_summary_block"]["included"] is False
    assert data["risk_summary_block"]["included"] is False


def test_advisory_evidence_package_similar_pattern_options() -> None:
    response = client.get(
        "/advisory/evidence-package/10010?include_candle_reference=true&include_similar_patterns=true&pattern_window=0&similar_case_limit=1000&pattern_ma=999"
    )
    assert response.status_code == 200
    data = response.json()
    block = data["price_candle_reference"]["similar_pattern_cases"]
    assert block["included"] is True
    assert block["pattern_window"] == 20
    assert block["requested_limit"] == 20
    assert block["pattern_ma"] == 20


def test_advisory_evidence_package_technical_indicator_toggle() -> None:
    response = client.get("/advisory/evidence-package/10010?include_technical_indicators=false")
    assert response.status_code == 200
    data = response.json()
    assert data["technical_indicators_block"]["included"] is False


def test_advisory_evidence_package_technical_indicator_source_metadata() -> None:
    response = client.get("/advisory/evidence-package/10010?include_technical_indicators=true")
    assert response.status_code == 200
    data = response.json()
    block = data["technical_indicators_block"]
    assert block["included"] is True
    assert block["source"] in {"stored", "calculated_fallback"}
    assert block["calculation_version"] == "v1"


def test_advisory_evidence_package_data_freshness_block() -> None:
    response = client.get("/advisory/evidence-package/10010")
    assert response.status_code == 200
    data = response.json()
    freshness = data.get("data_freshness_block")
    assert freshness is not None
    assert "package_generated_at" in freshness
    assert "price" in freshness
    assert "market_metrics" in freshness
    assert "technical_indicators" in freshness
    assert "overall_data_confidence" in freshness


def test_advisory_evidence_package_executive_summary_block() -> None:
    response = client.get("/advisory/evidence-package/10010")
    assert response.status_code == 200
    data = response.json()
    summary = data.get("executive_summary_for_gpt")
    assert summary is not None
    assert "summary_ko" in summary
    assert "key_points" in summary
    assert "analyst_focus_points" in summary
    assert "caution_points" in summary
    assert summary.get("data_confidence_level") in {"high", "medium", "low", "unknown"}
    assert "generated_basis" in summary


def test_advisory_evidence_package_executive_summary_generated_basis_with_options_off() -> None:
    response = client.get(
        "/advisory/evidence-package/10010?include_technical_indicators=false&include_news_disclosures_risk=false&include_similar_patterns=false"
    )
    assert response.status_code == 200
    summary = response.json().get("executive_summary_for_gpt", {})
    basis = summary.get("generated_basis", {})
    assert basis.get("technical_indicators") is False
    assert basis.get("news_disclosures_risk") is False
