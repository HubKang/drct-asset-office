from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient


def test_health(isolated_api_client: TestClient) -> None:
    client = isolated_api_client
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_and_list_stocks(isolated_api_client: TestClient) -> None:
    client = isolated_api_client
    code = f"T{uuid4().hex[:6].upper()}"
    payload = {
        "stock_code": code,
        "stock_name": "테스트종목",
        "market": "KOSPI",
        "sector": "IT",
        "industry": "SW",
    }
    create_resp = client.post("/stocks", json=payload)
    assert create_resp.status_code == 201
    list_resp = client.get("/stocks", params={"keyword": code})
    assert list_resp.status_code == 200
    assert any(item["stock_code"] == code for item in list_resp.json())
