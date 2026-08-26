from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_calculate_technical_indicator_single_stock() -> None:
    response = client.post("/technical-indicators/calculate/stock/10010")
    assert response.status_code == 200
    data = response.json()
    assert data["stock_id"] == 10010
    assert data["calculated_count"] >= 0
    assert data["saved_count"] >= 0
    assert "latest_trade_date" in data


def test_calculate_technical_indicator_selected_stocks() -> None:
    response = client.post("/technical-indicators/calculate/selected", json={"stock_ids": [10010, 10803]})
    assert response.status_code == 200
    data = response.json()
    assert data["total_requested"] == 2
    assert data["success_count"] + data["failed_count"] == 2
    assert isinstance(data["items"], list)


def test_daily_price_response_includes_technical_indicator_fields() -> None:
    response = client.get("/stock-prices/10010/daily?source=pykrx&limit=5&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) > 0
    first = data["items"][0]
    assert "rsi14" in first
    assert "macd_histogram" in first
    assert "bb_close_position" in first
    assert "atr14_ratio_to_close" in first
    assert "ma20_gap_pct" in first
    assert "volume_5_20_ratio" in first
    assert "technical_indicator_source" not in first
