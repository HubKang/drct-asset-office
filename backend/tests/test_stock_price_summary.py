from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def _assert_fact_only_summary(data: dict) -> None:
    assert data["source"] == "pykrx"
    assert data["price_count"] > 0
    assert data["latest_trade_date"]
    assert data["latest_close_price"] is not None
    assert "latest_ma5" in data
    assert "latest_ma20" in data
    assert "latest_ma60" in data
    assert "trading_value" not in data
    assert "latest_trading_value" not in data

    payload_text = str(data)
    assert "매수" not in payload_text
    assert "매도" not in payload_text
    assert "buy" not in payload_text.lower()
    assert "sell" not in payload_text.lower()


def test_stock_price_summary_for_dongwha() -> None:
    response = client.get("/stock-prices/10010/summary")
    assert response.status_code == 200
    data = response.json()
    _assert_fact_only_summary(data)
    assert data["stock_id"] == 10010
    assert data["latest_trade_date"] in {"2026-05-12", "2026-05-13"}


def test_stock_price_summary_for_dosan_robotics() -> None:
    response = client.get("/stock-prices/10803/summary")
    assert response.status_code == 200
    data = response.json()
    _assert_fact_only_summary(data)
    assert data["stock_id"] == 10803
    assert data["latest_trade_date"] in {"2026-05-12", "2026-05-13"}


def test_stock_price_summary_returns_404_for_missing_stock() -> None:
    response = client.get("/stock-prices/99999999/summary")
    assert response.status_code == 404
    assert response.json()["detail"] in {"stock not found", "stock price summary not found"}
