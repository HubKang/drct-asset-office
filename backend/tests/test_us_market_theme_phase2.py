from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.clients.kiwoom.kiwoom_models import KiwoomRestResponse
from backend.app.providers.market_data.kiwoom_us_daily_price_provider import KiwoomUsDailyPriceProvider, UsDailyPrice, UsDailyPriceFetchResult, UsHistoricalPricePartialError
from backend.app.services import us_market_data_service
from backend.app.services.realtime_theme_service import calculate_theme_strength


class _PagedClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def post_json(self, path: str, **kwargs) -> KiwoomRestResponse:
        self.calls.append({"path": path, **kwargs})
        page = len(self.calls)
        rows = [{"dt": "20260820", "cur_prc": "100.50", "open_pric": "99", "high_pric": "102", "low_pric": "98", "acc_trde_qty": "1,234"}] if page == 1 else [{"dt": "20260819", "cur_prc": "98", "open_pric": "97", "high_pric": "99", "low_pric": "96", "acc_trde_qty": "900"}]
        return KiwoomRestResponse(200, {}, {"result_list": rows, "unused": {"raw": "transient"}}, "", 1, "Y" if page == 1 else "N", "next-1" if page == 1 else "")


def test_kiwoom_usa06012_contract_parsing_and_continuation() -> None:
    client = _PagedClient()
    rows = KiwoomUsDailyPriceProvider(client=client).fetch(symbol="NVDA", exchange="NASDAQ", start_date="2026-08-21", trading_days=2)
    assert [row.trade_date for row in rows] == ["2026-08-19", "2026-08-20"]
    assert rows[-1].close_price == 100.5 and rows[-1].volume == 1234
    assert client.calls[0]["path"] == "/api/us/chart"
    assert client.calls[0]["api_id"] == "usa06012"
    assert client.calls[0]["body"] == {"stex_tp": "ND", "stk_cd": "NVDA", "strt_dt": "20260821", "upd_stkpc_tp": "1", "exrt_appl_tp": "0"}
    assert client.calls[1]["cont_yn"] == "Y" and client.calls[1]["next_key"] == "next-1"
    assert KiwoomUsDailyPriceProvider.exchange_code("NYSE") == "NY"
    assert KiwoomUsDailyPriceProvider.exchange_code("NYSE_AMERICAN") == "NA"


def test_phase2_migration_constraints() -> None:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript("""
        CREATE TABLE us_stocks (id INTEGER PRIMARY KEY);
        CREATE TABLE us_themes (id INTEGER PRIMARY KEY);
        INSERT INTO us_stocks VALUES (1); INSERT INTO us_themes VALUES (1);
    """)
    connection.executescript(Path("backend/app/sql/migrations/039_us_market_theme_price_returns.sql").read_text(encoding="utf-8"))
    values = (1, "2026-08-20", 10, 11, 9, 10.5, 100, "now", "now", "now")
    connection.execute("INSERT INTO us_stock_daily_prices(us_stock_id,trade_date,open_price,high_price,low_price,close_price,volume,collected_at,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)", values)
    try:
        connection.execute("INSERT INTO us_stock_daily_prices(us_stock_id,trade_date,open_price,high_price,low_price,close_price,volume,collected_at,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)", values)
        raise AssertionError("duplicate should fail")
    except sqlite3.IntegrityError:
        pass
    connection.close()


def _stock(client: TestClient, symbol: str, stock_type: str = "COMMON") -> dict:
    response = client.post("/us-stocks", json={"symbol": symbol, "exchange": "NASDAQ", "stock_type": stock_type, "is_active": 1})
    assert response.status_code == 201
    return response.json()


def test_price_upsert_theme_return_and_strength_parity(isolated_api_client: TestClient, monkeypatch) -> None:
    client = isolated_api_client
    a, b, etf = _stock(client, "AAA"), _stock(client, "BBB"), _stock(client, "ETF1", "ETF")
    group = client.post("/us-market-themes/groups", json={"name": "미국 AI", "sort_order": 1}).json()
    theme = client.post("/us-market-themes/themes", json={"theme_group_id": group["id"], "name": "AI 인프라", "sort_order": 1}).json()
    for stock, role in ((a, "LEADER"), (b, "CORE"), (etf, "ETF")):
        assert client.post(f"/us-market-themes/themes/{theme['id']}/stocks", json={"us_stock_id": stock["id"], "role": role, "is_representative": int(role == "LEADER"), "sort_order": 1}).status_code == 201
    group_counts = client.get("/us-market-themes/groups").json()[0]
    assert group_counts["active_theme_count"] == 1
    assert group_counts["theme_count"] == 1
    assert group_counts["linked_stock_count"] == 3

    samples = {
        "AAA": [("2026-08-18", 100), ("2026-08-19", 110), ("2026-08-20", 121)],
        "BBB": [("2026-08-18", 200), ("2026-08-19", 190), ("2026-08-20", 209)],
        "ETF1": [("2026-08-18", 50), ("2026-08-19", 100), ("2026-08-20", 200)],
    }

    def fake_fetch(_self, *, symbol: str, **_kwargs):
        return UsDailyPriceFetchResult([UsDailyPrice(day, close, close, close, close, 1000) for day, close in samples[symbol]], history_exhausted=True)

    monkeypatch.setattr(us_market_data_service.YFinanceUsDailyPriceProvider, "fetch_history", fake_fetch)
    first = client.post("/us-stocks/prices/collect", json={"mode": "BACKFILL", "trading_days": 260})
    assert first.status_code == 200
    assert first.json()["inserted_count"] == 9
    second = client.post("/us-stocks/prices/collect", json={"mode": "BACKFILL", "trading_days": 260})
    assert second.json()["inserted_count"] == 0 and second.json()["unchanged_count"] == 9

    recalculated = client.post("/us-market-themes/returns/recalculate", json={})
    assert recalculated.status_code == 200 and recalculated.json()["upserted_count"] == 2
    latest = client.get("/us-market-themes/returns/latest").json()
    item = latest["items"][0]
    values = [10.0, 10.0]
    assert item["trade_date"] == "2026-08-20"
    assert round(item["simple_return"], 6) == 10.0
    assert round(item["theme_strength"], 6) == round(calculate_theme_strength(values, 10.0), 6)
    assert item["breadth_ratio"] == 1.0 and item["valid_stock_count"] == 2

    treemap = client.get("/us-market-themes/treemap")
    assert treemap.status_code == 200
    treemap_body = treemap.json()
    assert treemap_body["latest_date"] == "2026-08-20"
    assert treemap_body["active_theme_count"] == 1
    assert treemap_body["linked_stock_count"] == 3
    assert treemap_body["aggregated_stock_count"] == 2
    assert treemap_body["items"][0]["linked_stock_count"] == 3
    assert treemap_body["items"][0]["theme_strength"] == item["theme_strength"]

    trend = client.get("/us-market-themes/returns/trend", params={"period": 30})
    assert trend.status_code == 200
    assert len(trend.json()["dates"]) == 30
    assert trend.json()["dates"][0] == "2026-07-22"
    assert trend.json()["dates"][-1] == "2026-08-20"
    assert "2026-08-18" in trend.json()["dates"]
    assert trend.json()["items"][0]["theme_group_id"] == group["id"]
    assert trend.json()["items"][0]["active"] == 1
    assert trend.json()["items"][0]["points"][-1]["valid_stock_count"] == 2
    points = trend.json()["items"][0]["points"]
    assert points[-1]["rolling_30d_simple_return"] == round(sum(point["simple_return"] for point in points), 4)
    assert points[-1]["rolling_30d_theme_strength"] == round(sum(point["theme_strength"] for point in points), 4)
    assert points[-1]["rolling_30d_valid_count"] == len(points)
    cutoff = client.get("/us-market-themes/returns/trend", params={"period": 30, "end_date": "2026-08-19"}).json()
    assert len(cutoff["dates"]) == 30
    assert cutoff["dates"][0] == "2026-07-21"
    assert cutoff["dates"][-1] == "2026-08-19"
    assert cutoff["items"][0]["points"][0]["rolling_30d_simple_return"] == points[0]["simple_return"]
    detail = client.get(f"/us-market-themes/themes/{theme['id']}/returns/2026-08-20").json()
    assert len(detail["stocks"]) == 3
    assert next(row for row in detail["stocks"] if row["symbol"] == "ETF1")["role"] == "ETF"

    missing = _stock(client, "NOPRICE")
    assert client.post(
        f"/us-market-themes/themes/{theme['id']}/stocks",
        json={"us_stock_id": missing["id"], "role": "RELATED", "sort_order": 9},
    ).status_code == 201
    latest_detail_response = client.get(f"/us-market-themes/themes/{theme['id']}/detail")
    assert latest_detail_response.status_code == 200
    latest_detail = latest_detail_response.json()
    assert latest_detail["trade_date"] == "2026-08-20"
    assert latest_detail["theme_group_name"] == "미국 AI"
    assert latest_detail["simple_return"] == item["simple_return"]
    assert latest_detail["theme_strength"] == item["theme_strength"]
    assert latest_detail["valid_stock_count"] == 2
    assert latest_detail["eligible_stock_count"] == 3
    assert latest_detail["linked_stock_count"] == 4
    assert [row["symbol"] for row in latest_detail["stocks"]] == ["AAA", "BBB", "NOPRICE", "ETF1"]
    no_price = next(row for row in latest_detail["stocks"] if row["symbol"] == "NOPRICE")
    assert no_price["close_price"] is None and no_price["daily_return"] is None
    assert no_price["exchange"] == "NASDAQ" and no_price["naver_code"] is None

    historical_detail = client.get(
        f"/us-market-themes/themes/{theme['id']}/detail",
        params={"trade_date": "2026-08-19"},
    ).json()
    assert historical_detail["trade_date"] == "2026-08-19"
    assert round(next(row for row in historical_detail["stocks"] if row["symbol"] == "AAA")["daily_return"], 6) == 10.0
    assert round(next(row for row in historical_detail["stocks"] if row["symbol"] == "BBB")["daily_return"], 6) == -5.0

    empty_theme = client.post(
        "/us-market-themes/themes",
        json={"theme_group_id": group["id"], "name": "집계 전 테마", "sort_order": 99},
    ).json()
    empty_detail = client.get(f"/us-market-themes/themes/{empty_theme['id']}/detail").json()
    assert empty_detail["trade_date"] is None
    assert empty_detail["simple_return"] is None and empty_detail["stocks"] == []

    listing = client.get("/us-stocks").json()["items"]
    aaa = next(row for row in listing if row["symbol"] == "AAA")
    assert aaa["latest_price_date"] == "2026-08-20" and aaa["price_status"] == "COMPLETE"


def test_missing_collection_calls_only_stocks_without_prices(isolated_api_client: TestClient, monkeypatch) -> None:
    client = isolated_api_client
    existing = _stock(client, "EXIST")
    calls: list[str] = []

    def fake_history(_self, *, symbol: str, **_kwargs):
        calls.append(symbol)
        return UsDailyPriceFetchResult([UsDailyPrice("2026-08-20", 10, 10, 10, 10, 100)], history_exhausted=True)

    monkeypatch.setattr(us_market_data_service.YFinanceUsDailyPriceProvider, "fetch_history", fake_history)
    assert client.post("/us-stocks/prices/collect", json={"mode": "SELECTED", "stock_ids": [existing["id"]]}).json()["requested_stock_count"] == 1
    missing = _stock(client, "NEWONE")
    result = client.post("/us-stocks/prices/collect", json={"mode": "MISSING"}).json()
    assert result["requested_stock_count"] == 1
    assert calls == ["EXIST", "NEWONE"]
    assert client.get("/us-stocks", params={"keyword": "NEWONE"}).json()["items"][0]["historical_price_status"] == "COMPLETE"
    empty = client.post("/us-stocks/prices/collect", json={"mode": "MISSING"}).json()
    assert empty["requested_stock_count"] == 0
    assert empty["message"] == "과거가격 수집이 필요한 종목이 없습니다."
    assert calls == ["EXIST", "NEWONE"]


def test_partial_history_is_preserved_and_retry_completes(isolated_api_client: TestClient, monkeypatch) -> None:
    client = isolated_api_client
    stock = _stock(client, "PART")
    attempts = 0

    def fake_history(_self, **_kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise UsHistoricalPricePartialError([UsDailyPrice("2026-08-19", 9, 9, 9, 9, 90)], "page_2_failed")
        return UsDailyPriceFetchResult([
            UsDailyPrice("2026-08-19", 9, 9, 9, 9, 90),
            UsDailyPrice("2026-08-20", 10, 10, 10, 10, 100),
        ], history_exhausted=True)

    monkeypatch.setattr(us_market_data_service.YFinanceUsDailyPriceProvider, "fetch_history", fake_history)
    first = client.post("/us-stocks/prices/collect", json={"mode": "SELECTED", "stock_ids": [stock["id"]]}).json()
    assert first["failed_stock_count"] == 1 and first["inserted_count"] == 1
    row = client.get("/us-stocks", params={"keyword": "PART"}).json()["items"][0]
    assert row["historical_price_status"] == "PARTIAL" and row["historical_price_row_count"] == 1
    second = client.post("/us-stocks/prices/collect", json={"mode": "SELECTED", "stock_ids": [stock["id"]]}).json()
    assert second["success_stock_count"] == 1
    row = client.get("/us-stocks", params={"keyword": "PART"}).json()["items"][0]
    assert row["historical_price_status"] == "COMPLETE" and row["historical_price_row_count"] == 2


def test_selected_targets_and_only_linked_themes_are_recalculated(isolated_api_client: TestClient, monkeypatch) -> None:
    client = isolated_api_client
    selected = _stock(client, "SEL1")
    other = _stock(client, "SEL2")
    _stock(client, "SKIP")
    group = client.post("/us-market-themes/groups", json={"name": "선택 수집", "sort_order": 1}).json()
    theme_a = client.post("/us-market-themes/themes", json={"theme_group_id": group["id"], "name": "테마 A", "sort_order": 1}).json()
    client.post("/us-market-themes/themes", json={"theme_group_id": group["id"], "name": "테마 B", "sort_order": 2})
    client.post(f"/us-market-themes/themes/{theme_a['id']}/stocks", json={"us_stock_id": selected["id"], "role": "CORE", "sort_order": 1})
    calls: list[str] = []

    def fake_history(_self, *, symbol: str, **_kwargs):
        calls.append(symbol)
        return UsDailyPriceFetchResult([
            UsDailyPrice("2026-08-19", 9, 9, 9, 9, 90),
            UsDailyPrice("2026-08-20", 10, 10, 10, 10, 100),
        ], history_exhausted=True)

    monkeypatch.setattr(us_market_data_service.YFinanceUsDailyPriceProvider, "fetch_history", fake_history)
    result = client.post("/us-stocks/prices/collect", json={"mode": "SELECTED", "stock_ids": [selected["id"], other["id"]]}).json()
    assert result["requested_stock_count"] == 2 and set(calls) == {"SEL1", "SEL2"}
    assert result["recalculated_theme_count"] == 1


def test_all_active_and_incremental_target_rules(isolated_api_client: TestClient, monkeypatch) -> None:
    client = isolated_api_client
    with_price = _stock(client, "HISTORY")
    _stock(client, "EMPTY")
    inactive = _stock(client, "INACTIVE")
    client.patch(f"/us-stocks/{inactive['id']}", json={"is_active": 0})
    calls: list[str] = []

    def fake_history(_self, *, symbol: str, **_kwargs):
        calls.append(symbol)
        return UsDailyPriceFetchResult([UsDailyPrice("2026-08-20", 10, 10, 10, 10, 100)], history_exhausted=True)

    monkeypatch.setattr(us_market_data_service.YFinanceUsDailyPriceProvider, "fetch_history", fake_history)
    client.post("/us-stocks/prices/collect", json={"mode": "SELECTED", "stock_ids": [with_price["id"]]})
    calls.clear()
    incremental = client.post("/us-stocks/prices/collect", json={"mode": "INCREMENTAL"}).json()
    assert incremental["requested_stock_count"] == 1
    assert calls == ["HISTORY"]
    calls.clear()
    all_active = client.post("/us-stocks/prices/collect", json={"mode": "ALL_ACTIVE"}).json()
    assert all_active["requested_stock_count"] == 2
    assert set(calls) == {"HISTORY", "EMPTY"}
    assert "INACTIVE" not in calls


def test_selected_incremental_collects_only_selected_stock_and_provides_return(isolated_api_client: TestClient, monkeypatch) -> None:
    client = isolated_api_client
    selected = _stock(client, "ALB")
    _stock(client, "OTHER")
    calls: list[tuple[str, int]] = []

    def fake_history(_self, *, symbol: str, trading_days: int, **_kwargs):
        calls.append((symbol, trading_days))
        return UsDailyPriceFetchResult([
            UsDailyPrice("2026-08-19", 98, 99, 97, 98, 900),
            UsDailyPrice("2026-08-20", 100, 102, 99, 100, 1000),
        ], history_exhausted=False)

    monkeypatch.setattr(us_market_data_service.YFinanceUsDailyPriceProvider, "fetch_history", fake_history)
    result = client.post("/us-stocks/prices/collect", json={"mode": "INCREMENTAL", "stock_ids": [selected["id"]]}).json()
    assert result["requested_stock_count"] == 1
    assert result["success_stock_count"] == 1
    assert result["inserted_count"] == 2
    assert calls == [("ALB", 2)]
    row = client.get("/us-stocks", params={"keyword": "ALB"}).json()["items"][0]
    assert row["latest_close"] == 100
    assert round(row["latest_change_rate"], 4) == 2.0408
    assert row["historical_price_status"] == "PARTIAL"
    assert row["historical_price_row_count"] == 2


def test_historical_collection_saves_valid_rows_and_marks_partial_when_provider_skips_null_candle(isolated_api_client: TestClient, monkeypatch) -> None:
    client = isolated_api_client
    stock = _stock(client, "PARTIALNULL")
    attempts = 0

    def fake_history(_self, **_kwargs):
        nonlocal attempts
        attempts += 1
        return UsDailyPriceFetchResult(
            [
                UsDailyPrice("2026-08-26", 98, 101, 97, 100, 900),
                UsDailyPrice("2026-08-27", 100, 103, 99, 102, 1_000),
                *([UsDailyPrice("2026-08-28", 102, 105, 101, 104, 1_100)] if attempts > 1 else []),
            ],
            history_exhausted=True,
            incomplete_row_count=1 if attempts == 1 else 0,
        )

    monkeypatch.setattr(us_market_data_service.YFinanceUsDailyPriceProvider, "fetch_history", fake_history)
    result = client.post(
        "/us-stocks/prices/collect",
        json={"mode": "SELECTED", "stock_ids": [stock["id"]], "trading_days": 260},
    ).json()

    assert result["inserted_count"] == 2
    assert result["success_stock_count"] == 0
    assert result["failed_stock_count"] == 1
    assert "결측 일봉 1건" in result["failures"][0]["reason"]
    row = client.get("/us-stocks", params={"keyword": "PARTIALNULL"}).json()["items"][0]
    assert row["historical_price_status"] == "PARTIAL"
    assert row["historical_price_row_count"] == 2

    repaired = client.post("/us-stocks/prices/collect", json={"mode": "INCREMENTAL", "stock_ids": [stock["id"]]}).json()
    assert repaired["inserted_count"] == 1
    repaired_row = client.get("/us-stocks", params={"keyword": "PARTIALNULL"}).json()["items"][0]
    assert repaired_row["historical_price_status"] == "COMPLETE"
    assert repaired_row["historical_price_row_count"] == 3


def test_incremental_collection_refreshes_provisional_latest_trading_day(isolated_api_client: TestClient, monkeypatch) -> None:
    client = isolated_api_client
    coin = _stock(client, "COIN")
    attempts = 0

    def fake_history(_self, **_kwargs):
        nonlocal attempts
        attempts += 1
        latest_close = 183.671 if attempts == 1 else 187.18
        return UsDailyPriceFetchResult([
            UsDailyPrice("2026-08-24", 179.48, 179.48, 179.48, 179.48, 1_000),
            UsDailyPrice("2026-08-25", latest_close, latest_close, latest_close, latest_close, 2_000),
        ], history_exhausted=False)

    monkeypatch.setattr(us_market_data_service.YFinanceUsDailyPriceProvider, "fetch_history", fake_history)
    first = client.post("/us-stocks/prices/collect", json={"mode": "INCREMENTAL", "stock_ids": [coin["id"]]}).json()
    assert first["inserted_count"] == 2 and first["updated_count"] == 0

    second = client.post("/us-stocks/prices/collect", json={"mode": "INCREMENTAL", "stock_ids": [coin["id"]]}).json()
    assert second["inserted_count"] == 0 and second["updated_count"] == 1 and second["unchanged_count"] == 1
    assert second["affected_date_from"] == "2026-08-25"
    assert second["affected_date_to"] == "2026-08-25"

    row = client.get("/us-stocks", params={"keyword": "COIN"}).json()["items"][0]
    assert row["latest_price_date"] == "2026-08-25"
    assert row["latest_close"] == 187.18
    assert row["latest_change_rate"] == 4.2902
    assert row["historical_price_row_count"] == 2


def test_incremental_collection_overlaps_two_sessions_and_inserts_a_new_session(isolated_api_client: TestClient, monkeypatch) -> None:
    client = isolated_api_client
    stock = _stock(client, "OVERLAP")
    attempts = 0

    def fake_history(_self, **_kwargs):
        nonlocal attempts
        attempts += 1
        if attempts > 1:
            rows = [
                UsDailyPrice("2026-08-21", 90, 91, 89, 90, 900),
                UsDailyPrice("2026-08-24", 100, 101, 99, 100, 1_000),
                UsDailyPrice("2026-08-25", 112, 114, 108, 113, 1_300),
                UsDailyPrice("2026-08-26", 120, 121, 119, 120, 1_200),
            ]
        else:
            rows = [
                UsDailyPrice("2026-08-21", 90, 91, 89, 90, 900),
                UsDailyPrice("2026-08-24", 100, 101, 99, 100, 1_000),
                UsDailyPrice("2026-08-25", 110, 111, 109, 110, 1_100),
            ]
        return UsDailyPriceFetchResult(rows, history_exhausted=False)

    monkeypatch.setattr(us_market_data_service.YFinanceUsDailyPriceProvider, "fetch_history", fake_history)
    first = client.post("/us-stocks/prices/collect", json={"mode": "SELECTED", "stock_ids": [stock["id"]], "trading_days": 260}).json()
    assert first["inserted_count"] == 3

    second = client.post("/us-stocks/prices/collect", json={"mode": "INCREMENTAL", "stock_ids": [stock["id"]]}).json()
    assert second["inserted_count"] == 1 and second["updated_count"] == 1 and second["unchanged_count"] == 1
    prices = client.get(f"/us-stocks/{stock['id']}/prices").json()["items"]
    assert [row["trade_date"] for row in prices] == ["2026-08-21", "2026-08-24", "2026-08-25", "2026-08-26"]
    assert next(row for row in prices if row["trade_date"] == "2026-08-25")["close_price"] == 113


def test_incremental_collection_uses_provider_sessions_without_synthetic_weekend_rows(isolated_api_client: TestClient, monkeypatch) -> None:
    client = isolated_api_client
    stock = _stock(client, "WEEKEND")

    def fake_history(_self, **_kwargs):
        return UsDailyPriceFetchResult([
            UsDailyPrice("2026-08-27", 100, 101, 99, 100, 1_000),
            UsDailyPrice("2026-08-28", 101, 102, 100, 101, 1_100),
        ], history_exhausted=False)

    monkeypatch.setattr(us_market_data_service.YFinanceUsDailyPriceProvider, "fetch_history", fake_history)
    client.post("/us-stocks/prices/collect", json={"mode": "INCREMENTAL", "stock_ids": [stock["id"]]})
    second = client.post("/us-stocks/prices/collect", json={"mode": "INCREMENTAL", "stock_ids": [stock["id"]]}).json()
    assert second["inserted_count"] == 0 and second["updated_count"] == 0 and second["unchanged_count"] == 2
    prices = client.get(f"/us-stocks/{stock['id']}/prices").json()["items"]
    assert [row["trade_date"] for row in prices] == ["2026-08-27", "2026-08-28"]


def test_market_refresh_completes_linked_history_and_recalculates_all_active_themes(isolated_api_client: TestClient, monkeypatch) -> None:
    client = isolated_api_client
    a, b, c = _stock(client, "RFA"), _stock(client, "RFB"), _stock(client, "RFC")
    _stock(client, "UNLINKED")
    group = client.post("/us-market-themes/groups", json={"name": "전체 갱신", "sort_order": 1}).json()
    theme_a = client.post("/us-market-themes/themes", json={"theme_group_id": group["id"], "name": "갱신 A", "sort_order": 1}).json()
    theme_b = client.post("/us-market-themes/themes", json={"theme_group_id": group["id"], "name": "갱신 B", "sort_order": 2}).json()
    for theme, stock in ((theme_a, a), (theme_a, b), (theme_b, b), (theme_b, c)):
        client.post(f"/us-market-themes/themes/{theme['id']}/stocks", json={"us_stock_id": stock["id"], "role": "CORE", "sort_order": 1})
    calls: list[tuple[str, int]] = []

    def fake_history(_self, *, symbol: str, trading_days: int, **_kwargs):
        calls.append((symbol, trading_days))
        base = {"RFA": 100, "RFB": 200, "RFC": 300, "UNLINKED": 400}[symbol]
        return UsDailyPriceFetchResult([
            UsDailyPrice("2026-08-18", base, base, base, base, 100),
            UsDailyPrice("2026-08-19", base + 10, base + 10, base + 10, base + 10, 110),
            UsDailyPrice("2026-08-20", base + 20, base + 20, base + 20, base + 20, 120),
        ], history_exhausted=True)

    monkeypatch.setattr(us_market_data_service.YFinanceUsDailyPriceProvider, "fetch_history", fake_history)
    client.post("/us-stocks/prices/collect", json={"mode": "SELECTED", "stock_ids": [c["id"]], "trading_days": 260})
    calls.clear()
    response = client.post("/us-market-themes/refresh", json={"mode": "INCREMENTAL", "trading_days": 260})
    assert response.status_code == 200
    result = response.json()
    assert result["price"]["requested_stock_count"] == 3
    assert result["price"]["success_stock_count"] == 3
    assert result["returns"]["processed_theme_count"] == 2
    assert {symbol for symbol, _ in calls} == {"RFA", "RFB", "RFC"}
    assert "UNLINKED" not in {symbol for symbol, _ in calls}
    assert dict(calls)["RFA"] == 260 and dict(calls)["RFB"] == 260
    latest = client.get("/us-market-themes/returns/latest").json()
    assert {item["theme_id"] for item in latest["items"] if item["trade_date"] == "2026-08-20"} == {theme_a["id"], theme_b["id"]}


def test_group_refresh_updates_only_group_stocks_and_group_theme_returns(isolated_api_client: TestClient, monkeypatch) -> None:
    client = isolated_api_client
    a, b, c, d = (_stock(client, symbol) for symbol in ("GRA", "GRB", "GRC", "GRD"))
    group_a = client.post("/us-market-themes/groups", json={"name": "그룹 A", "sort_order": 1}).json()
    group_b = client.post("/us-market-themes/groups", json={"name": "그룹 B", "sort_order": 2}).json()
    theme_a = client.post("/us-market-themes/themes", json={"theme_group_id": group_a["id"], "name": "테마 A", "sort_order": 1}).json()
    theme_b = client.post("/us-market-themes/themes", json={"theme_group_id": group_b["id"], "name": "테마 B", "sort_order": 1}).json()
    for theme, stock in ((theme_a, a), (theme_a, b), (theme_b, c), (theme_b, d)):
        client.post(f"/us-market-themes/themes/{theme['id']}/stocks", json={"us_stock_id": stock["id"], "role": "CORE", "sort_order": 1})
    calls: list[str] = []

    def fake_history(_self, *, symbol: str, **_kwargs):
        calls.append(symbol)
        base = {"GRA": 100, "GRB": 200, "GRC": 300, "GRD": 400}[symbol]
        return UsDailyPriceFetchResult([
            UsDailyPrice("2026-08-27", base, base, base, base, 100),
            UsDailyPrice("2026-08-28", base + 10, base + 10, base + 10, base + 10, 110),
        ], history_exhausted=True)

    monkeypatch.setattr(us_market_data_service.YFinanceUsDailyPriceProvider, "fetch_history", fake_history)
    response = client.post(f"/us-market-themes/groups/{group_a['id']}/refresh", json={"mode": "INCREMENTAL", "trading_days": 260})

    assert response.status_code == 200
    result = response.json()
    assert result["price"]["requested_stock_count"] == 2
    assert result["returns"]["processed_theme_count"] == 1
    assert set(calls) == {"GRA", "GRB"}
    latest = client.get("/us-market-themes/returns/latest").json()["items"]
    assert next(item for item in latest if item["theme_id"] == theme_a["id"])["trade_date"] == "2026-08-28"
    assert next(item for item in latest if item["theme_id"] == theme_b["id"])["trade_date"] is None


def test_theme_refresh_updates_only_theme_stocks_and_theme_return(isolated_api_client: TestClient, monkeypatch) -> None:
    client = isolated_api_client
    a, b, c = (_stock(client, symbol) for symbol in ("TRA", "TRB", "TRC"))
    group = client.post("/us-market-themes/groups", json={"name": "테마 갱신 그룹", "sort_order": 1}).json()
    theme_a = client.post("/us-market-themes/themes", json={"theme_group_id": group["id"], "name": "갱신 대상", "sort_order": 1}).json()
    theme_b = client.post("/us-market-themes/themes", json={"theme_group_id": group["id"], "name": "비대상", "sort_order": 2}).json()
    for theme, stock in ((theme_a, a), (theme_a, b), (theme_b, c)):
        client.post(f"/us-market-themes/themes/{theme['id']}/stocks", json={"us_stock_id": stock["id"], "role": "CORE", "sort_order": 1})
    calls: list[str] = []

    def fake_history(_self, *, symbol: str, **_kwargs):
        calls.append(symbol)
        base = {"TRA": 100, "TRB": 200, "TRC": 300}[symbol]
        return UsDailyPriceFetchResult([
            UsDailyPrice("2026-08-27", base, base, base, base, 100),
            UsDailyPrice("2026-08-28", base + 10, base + 10, base + 10, base + 10, 110),
        ], history_exhausted=True)

    monkeypatch.setattr(us_market_data_service.YFinanceUsDailyPriceProvider, "fetch_history", fake_history)
    response = client.post(f"/us-market-themes/themes/{theme_a['id']}/refresh", json={"mode": "INCREMENTAL", "trading_days": 260})

    assert response.status_code == 200
    result = response.json()
    assert result["price"]["requested_stock_count"] == 2
    assert result["returns"]["processed_theme_count"] == 1
    assert set(calls) == {"TRA", "TRB"}
    latest = client.get("/us-market-themes/returns/latest").json()["items"]
    assert next(item for item in latest if item["theme_id"] == theme_a["id"])["trade_date"] == "2026-08-28"
    assert next(item for item in latest if item["theme_id"] == theme_b["id"])["trade_date"] is None
