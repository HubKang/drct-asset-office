from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_create_and_list_watchlist() -> None:
    code = f"W{uuid4().hex[:6]}"
    stock_resp = client.post(
        "/stocks",
        json={"stock_code": code, "stock_name": "워치테스트", "market": "KOSPI", "sector": "IT", "industry": "SW"},
    )
    assert stock_resp.status_code == 201
    stock_id = stock_resp.json()["id"]

    create_resp = client.post(
        "/watchlist",
        json={
            "stock_id": stock_id,
            "status": "관심",
            "interest_reason": "테스트",
            "entry_condition": "조건A",
            "exit_condition": "조건B",
            "risk_note": "리스크",
        },
    )
    assert create_resp.status_code == 201
    list_resp = client.get("/watchlist", params={"keyword": code})
    assert list_resp.status_code == 200
    assert any(item["stock_code"] == code for item in list_resp.json())
