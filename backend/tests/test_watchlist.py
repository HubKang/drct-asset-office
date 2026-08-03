from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient


def _create_stock(client: TestClient, code_prefix: str = "W", market: str = "KOSPI") -> int:
    code = f"{code_prefix}{uuid4().hex[:6].upper()}"
    response = client.post(
        "/stocks",
        json={"stock_code": code, "stock_name": f"Stock-{code}", "market": market, "sector": "IT", "industry": "SW"},
    )
    assert response.status_code == 201
    return int(response.json()["id"])


def test_create_and_list_watchlist(isolated_api_client: TestClient) -> None:
    client = isolated_api_client
    stock_id = _create_stock(client)

    create_resp = client.post(
        "/watchlist",
        json={
            "stock_id": stock_id,
            "status": "관심",
            "interest_reason": "core idea",
            "entry_condition": "condition A",
            "exit_condition": "condition B",
            "risk_note": "risk note",
        },
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["is_active"] == 1

    list_resp = client.get("/watchlist", params={"limit": 20, "offset": 0, "is_active": 1})
    assert list_resp.status_code == 200
    assert any(item["stock_id"] == stock_id for item in list_resp.json())


def test_watchlist_stock_ids_and_bulk_flow(isolated_api_client: TestClient) -> None:
    client = isolated_api_client
    stock_id_1 = _create_stock(client, "B", "KOSPI")
    stock_id_2 = _create_stock(client, "C", "KOSDAQ")

    bulk_resp = client.post(
        "/watchlist/bulk",
        json={"stock_ids": [stock_id_1, stock_id_2], "memo": "pool add"},
    )
    assert bulk_resp.status_code == 201
    assert bulk_resp.json()["inserted_count"] == 2
    assert bulk_resp.json()["reactivated_count"] == 0
    assert bulk_resp.json()["skipped_count"] == 0

    stock_ids_resp = client.get("/watchlist/stock-ids")
    assert stock_ids_resp.status_code == 200
    stock_ids = stock_ids_resp.json()["stock_ids"]
    assert stock_id_1 in stock_ids
    assert stock_id_2 in stock_ids

    duplicate_resp = client.post(
        "/watchlist/bulk",
        json={"stock_ids": [stock_id_1, stock_id_2], "memo": "pool add"},
    )
    assert duplicate_resp.status_code == 201
    assert duplicate_resp.json()["inserted_count"] == 0
    assert duplicate_resp.json()["reactivated_count"] == 0
    assert duplicate_resp.json()["skipped_count"] == 2


def test_watchlist_bulk_reactivates_inactive_item(isolated_api_client: TestClient) -> None:
    client = isolated_api_client
    stock_id = _create_stock(client, "R", "KOSPI")

    create_resp = client.post("/watchlist", json={"stock_id": stock_id, "status": "관심"})
    assert create_resp.status_code == 201
    watchlist_id = create_resp.json()["id"]

    delete_resp = client.delete(f"/watchlist/{watchlist_id}")
    assert delete_resp.status_code == 204

    inactive_list_resp = client.get("/watchlist", params={"is_active": 0, "limit": 20, "offset": 0})
    assert inactive_list_resp.status_code == 200
    assert any(item["stock_id"] == stock_id for item in inactive_list_resp.json())

    bulk_resp = client.post("/watchlist/bulk", json={"stock_ids": [stock_id], "memo": "reactivate"})
    assert bulk_resp.status_code == 201
    assert bulk_resp.json()["inserted_count"] == 0
    assert bulk_resp.json()["reactivated_count"] == 1
    assert bulk_resp.json()["skipped_count"] == 0

    active_list_resp = client.get("/watchlist", params={"is_active": 1, "limit": 20, "offset": 0})
    assert active_list_resp.status_code == 200
    assert any(item["stock_id"] == stock_id for item in active_list_resp.json())
