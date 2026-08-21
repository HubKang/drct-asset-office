from __future__ import annotations

from fastapi.testclient import TestClient


def test_us_stock_crud_filters_and_summary(isolated_api_client: TestClient) -> None:
    client = isolated_api_client
    created = client.post("/us-stocks", json={"symbol": "nvda", "name": "NVIDIA Corporation", "name_ko": "엔비디아", "exchange": "NASDAQ", "stock_type": "COMMON", "naver_code": None, "is_active": 1})
    assert created.status_code == 201
    stock = created.json()
    assert stock["symbol"] == "NVDA"
    assert stock["naver_code"] is None

    duplicate = client.post("/us-stocks", json={"symbol": "NVDA", "exchange": "NASDAQ"})
    assert duplicate.status_code == 409

    listing = client.get("/us-stocks", params={"keyword": "엔비", "exchange": "NASDAQ", "stock_type": "COMMON"})
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert client.get("/us-stocks", params={"price_status": "NOT_COLLECTED"}).json()["total"] == 1
    assert client.get("/us-stocks", params={"price_status": "COMPLETE"}).json()["total"] == 0

    updated = client.patch(f"/us-stocks/{stock['id']}", json={"is_active": 0, "name_ko": "엔비디아 수정"})
    assert updated.status_code == 200
    assert updated.json()["is_active"] == 0

    summary = client.get("/us-stocks/summary").json()
    assert summary == {"total": 1, "active": 0, "common": 1, "etf": 0, "price_complete": 0, "price_not_collected": 0, "price_partial": 0, "price_error": 0, "latest_price_date": None}


def test_us_stock_bulk_preview_and_create(isolated_api_client: TestClient) -> None:
    client = isolated_api_client
    payload = {"tickers": ["NVDA", "AMD", "AVGO", "MU", "SMH", "SOXX", "amd", "BAD SYMBOL"], "exchange": "NASDAQ", "stock_type": "ETF", "is_active": 1}
    preview = client.post("/us-stocks/bulk/preview", json=payload)
    assert preview.status_code == 200
    assert [row["status"] for row in preview.json()["items"]] == ["NEW", "NEW", "NEW", "NEW", "NEW", "NEW", "DUPLICATE", "INVALID"]

    created = client.post("/us-stocks/bulk", json=payload)
    assert created.status_code == 201
    assert created.json()["created_count"] == 6
    assert created.json()["skipped_count"] == 2

    second = client.post("/us-stocks/bulk/preview", json={"tickers": ["AMD"], "exchange": "NASDAQ", "stock_type": "ETF"})
    assert second.json()["items"][0]["status"] == "EXISTING"


def test_us_stock_physical_delete_removes_theme_links(isolated_api_client: TestClient) -> None:
    client = isolated_api_client
    stock = client.post("/us-stocks", json={"symbol": "ABB", "exchange": "NYSE", "stock_type": "COMMON", "is_active": 1}).json()
    group = client.post("/us-market-themes/groups", json={"name": "산업재", "sort_order": 1, "active": 1}).json()
    theme = client.post("/us-market-themes/themes", json={"theme_group_id": group["id"], "name": "전력기기", "keywords": [], "sort_order": 1, "active": 1}).json()
    mapping = client.post(f"/us-market-themes/themes/{theme['id']}/stocks", json={"us_stock_id": stock["id"], "role": "RELATED"})
    assert mapping.status_code == 201

    impact = client.get(f"/us-stocks/{stock['id']}/delete-impact")
    assert impact.status_code == 200
    assert impact.json() == {"stock_id": stock["id"], "symbol": "ABB", "price_row_count": 0, "theme_link_count": 1, "affected_theme_count": 1}

    rejected = client.delete(f"/us-stocks/{stock['id']}", params={"confirm_symbol": "AB"})
    assert rejected.status_code == 422
    assert client.get("/us-stocks", params={"keyword": "ABB"}).json()["total"] == 1

    deleted = client.delete(f"/us-stocks/{stock['id']}", params={"confirm_symbol": "ABB"})
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert deleted.json()["deleted_theme_link_count"] == 1
    assert client.get("/us-stocks", params={"keyword": "ABB"}).json()["total"] == 0
    assert client.get(f"/us-market-themes/themes/{theme['id']}/stocks").json() == []
