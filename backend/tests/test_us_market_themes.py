from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.services import us_stock_service


def test_us_market_theme_migration_constraints() -> None:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript("CREATE TABLE us_stocks (id INTEGER PRIMARY KEY, symbol TEXT NOT NULL); INSERT INTO us_stocks(id, symbol) VALUES (1, 'NVDA');")
    migration = Path("backend/app/sql/migrations/038_us_market_themes.sql").read_text(encoding="utf-8")
    connection.executescript(migration)
    connection.execute("INSERT INTO us_theme_groups(name, created_at, updated_at) VALUES ('반도체', 'now', 'now')")
    connection.execute("INSERT INTO us_themes(theme_group_id, name, created_at, updated_at) VALUES (1, 'AI반도체/GPU', 'now', 'now')")
    connection.execute("INSERT INTO us_theme_stocks(theme_id, us_stock_id, role, created_at, updated_at) VALUES (1, 1, 'LEADER', 'now', 'now')")
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute("INSERT INTO us_theme_stocks(theme_id, us_stock_id, role, created_at, updated_at) VALUES (1, 1, 'CORE', 'now', 'now')")
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute("INSERT INTO us_theme_stocks(theme_id, us_stock_id, role, created_at, updated_at) VALUES (1, 999, 'RELATED', 'now', 'now')")
    connection.close()


def _create_stock(client: TestClient, symbol: str, exchange: str = "NASDAQ", naver_code: str | None = None) -> dict:
    response = client.post("/us-stocks", json={"symbol": symbol, "name": f"{symbol} Inc.", "name_ko": symbol, "exchange": exchange, "stock_type": "COMMON", "naver_code": naver_code, "is_active": 1})
    assert response.status_code == 201
    return response.json()


def test_us_theme_crud_nm_mapping_and_summary(isolated_api_client: TestClient) -> None:
    client = isolated_api_client
    nvda = _create_stock(client, "NVDA", naver_code="NVDA.O")
    avgo = _create_stock(client, "AVGO", naver_code="AVGO.O")

    group = client.post("/us-market-themes/groups", json={"name": "반도체", "description": "미국 반도체", "sort_order": 1, "active": 1})
    assert group.status_code == 201
    group_id = group.json()["id"]
    duplicate_group = client.post("/us-market-themes/groups", json={"name": "반도체", "sort_order": 2, "active": 1})
    assert duplicate_group.status_code == 409

    gpu = client.post("/us-market-themes/themes", json={"theme_group_id": group_id, "name": "AI반도체/GPU", "keywords": ["AI", "GPU", "AI"], "sort_order": 1, "active": 1})
    network = client.post("/us-market-themes/themes", json={"theme_group_id": group_id, "name": "AI서버·네트워크", "keywords": ["network"], "sort_order": 2, "active": 1})
    assert gpu.status_code == 201 and network.status_code == 201
    assert gpu.json()["keywords"] == ["AI", "GPU"]

    first = client.post(f"/us-market-themes/themes/{gpu.json()['id']}/stocks", json={"us_stock_id": nvda["id"], "role": "LEADER", "is_representative": 1, "sort_order": 1})
    second = client.post(f"/us-market-themes/themes/{gpu.json()['id']}/stocks", json={"us_stock_id": avgo["id"], "role": "CORE", "is_representative": 0, "sort_order": 2})
    other_theme = client.post(f"/us-market-themes/themes/{network.json()['id']}/stocks", json={"us_stock_id": avgo["id"], "role": "CORE", "is_representative": 1, "sort_order": 1})
    assert first.status_code == second.status_code == other_theme.status_code == 201
    assert client.post(f"/us-market-themes/themes/{gpu.json()['id']}/stocks", json={"us_stock_id": nvda["id"]}).status_code == 409

    summary = client.get("/us-market-themes/summary").json()
    assert summary == {"theme_groups": 1, "themes": 2, "active_themes": 2, "linked_stocks": 2}
    themes = client.get("/us-market-themes/themes").json()
    assert next(row for row in themes if row["id"] == gpu.json()["id"])["representative_symbols"] == ["NVDA"]

    updated = client.patch(f"/us-market-themes/mappings/{second.json()['mapping_id']}", json={"role": "RELATED", "is_representative": 1})
    assert updated.status_code == 200 and updated.json()["role"] == "RELATED" and updated.json()["is_representative"] == 1
    unlinked = client.delete(f"/us-market-themes/mappings/{first.json()['mapping_id']}")
    assert unlinked.status_code == 200 and unlinked.json()["active"] == 0
    assert client.get("/us-stocks", params={"keyword": "NVDA"}).json()["total"] == 1


def test_us_naver_chart_fields_cache_and_safe_fallback(isolated_api_client: TestClient, monkeypatch) -> None:
    client = isolated_api_client
    us_stock_service._naver_chart_cache.clear()
    ceg = _create_stock(client, "CEG", exchange="NYSE", naver_code="CEG.N")
    missing = _create_stock(client, "NONE", exchange="NYSE", naver_code=None)
    calls: list[str] = []

    class Response:
        def raise_for_status(self) -> None: pass
        def json(self) -> dict:
            return {"imageChartUrlInfo": {"candle": {"day": "https://img/day.png", "week": "https://img/week.png", "month": "https://img/month.png"}}, "unused": {"raw": "not returned"}}

    def fake_get(url: str, **_kwargs):
        calls.append(url)
        return Response()

    monkeypatch.setattr(us_stock_service.requests, "get", fake_get)
    first = client.get(f"/us-stocks/{ceg['id']}/naver-charts")
    second = client.get(f"/us-stocks/{ceg['id']}/naver-charts")
    assert first.status_code == 200
    assert first.json() == {"stock_id": ceg["id"], "naver_code": "CEG.N", "day": "https://img/day.png", "week": "https://img/week.png", "month": "https://img/month.png", "available": True}
    assert second.json() == first.json()
    assert len(calls) == 1 and calls[0].endswith("/CEG.N/basic")
    assert client.get(f"/us-stocks/{missing['id']}/naver-charts").json()["available"] is False


def test_us_naver_chart_metadata_failure_uses_direct_image_urls(isolated_api_client: TestClient, monkeypatch) -> None:
    client = isolated_api_client
    us_stock_service._naver_chart_cache.clear()
    stock = _create_stock(client, "TSLA", naver_code="TSLA.O")
    calls = 0

    def fake_get(_url: str, **_kwargs):
        nonlocal calls
        calls += 1
        raise us_stock_service.requests.RequestException("temporary failure")

    monkeypatch.setattr(us_stock_service.requests, "get", fake_get)
    result = client.get(f"/us-stocks/{stock['id']}/naver-charts").json()
    assert result["available"] is True
    assert result["day"].endswith("/day/TSLA.O_end.png")
    assert result["week"].endswith("/week/TSLA.O_end.png")
    assert result["month"].endswith("/month/TSLA.O_end.png")
    assert calls == 1
