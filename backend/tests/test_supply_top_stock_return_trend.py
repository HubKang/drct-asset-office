from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.schemas.external_kiwoom_schema import MonthlySupplyClassificationDiagnostics
from backend.app.services.external_kiwoom_service import ExternalKiwoomService


def test_top_stock_return_trend_uses_unique_supply_days_and_one_price_batch(monkeypatch) -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE stock_daily_prices (
                stock_id INTEGER NOT NULL,
                trade_date TEXT NOT NULL,
                close_price REAL,
                change_rate REAL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            """
            INSERT INTO stock_daily_prices (stock_id, trade_date, close_price, change_rate, updated_at) VALUES
              (1, '2026-06-30', 100, 0, '2026-07-27 09:01:00'),
              (1, '2026-07-01', 110, 10, '2026-07-27 09:01:00'),
              (1, '2026-07-02', 121, 10, '2026-07-27 09:01:00'),
              (2, '2026-07-02', 200, 2, '2026-07-26 15:00:00'),
              (3, '2026-06-30', 50, 0, '2026-07-27 09:02:00'),
              (3, '2026-07-01', 45, -10, '2026-07-27 09:02:00'),
              (3, '2026-07-03', 55, 22.2222, '2026-07-27 09:02:00')
            """
        )

    db = Session(engine)
    service = ExternalKiwoomService(db)
    records = [
        {"stock_id": 1, "stock_code": "000001", "stock_name": "가종목", "trade_date": day}
        for day in ("2026-07-01", "2026-07-01", "2026-07-02", "2026-07-03")
    ] + [
        {"stock_id": 2, "stock_code": "000002", "stock_name": "나종목", "trade_date": day}
        for day in ("2026-07-01", "2026-07-03")
    ] + [
        {"stock_id": 3, "stock_code": "000003", "stock_name": "다종목", "trade_date": day}
        for day in ("2026-07-01", "2026-07-02")
    ]
    diagnostics = MonthlySupplyClassificationDiagnostics(
        event_count=len(records), unique_stock_count=3, active_theme_count=1,
        reclassified_event_stock_count=0, unclassified_stock_count=0,
        period_start_date="2026-07-01", period_end_date="2026-07-03",
    )
    monkeypatch.setattr(service, "_build_supply_theme_aggregation", lambda *_: {"records": records, "diagnostics": diagnostics})

    price_select_count = 0

    def count_price_select(_conn, _cursor, statement, _parameters, _context, _executemany) -> None:
        nonlocal price_select_count
        if "FROM stock_daily_prices price" in statement:
            price_select_count += 1

    event.listen(engine, "before_cursor_execute", count_price_select)
    response = service.get_supply_top_stock_return_trend(
        period_start_date="2026-07-01", period_end_date="2026-07-03", limit=3,
    )

    assert price_select_count == 1
    assert [(item.stock_name, item.appearance_count) for item in response.stocks] == [
        ("가종목", 3), ("나종목", 2), ("다종목", 2),
    ]
    assert response.trade_dates == ["2026-07-01", "2026-07-02", "2026-07-03"]
    assert response.last_price_collection_date == "2026-07-26"
    first = response.stocks[0]
    assert first.base_price_date == "2026-06-30"
    assert first.base_close == 100
    assert first.latest_cumulative_return == 21
    assert first.has_sufficient_price_data is True
    assert response.stocks[1].price_data_status == "INSUFFICIENT_OBSERVATIONS"
    assert response.price_readiness.ready_stock_count == 2
    assert response.price_readiness.missing_stock_ids == [2]
    assert [point.trade_date for point in response.stocks[2].points] == ["2026-07-01", "2026-07-03"]
    assert response.stocks[2].latest_cumulative_return == 10
    db.close()


def test_price_refresh_targets_all_top_stocks_once(monkeypatch) -> None:
    from backend.app.schemas.external_kiwoom_schema import (
        SupplyTopStockPriceCollectRequest,
        SupplyTopStockPriceReadiness,
        SupplyTopStockReturnTrendItem,
        SupplyTopStockReturnTrendResponse,
    )
    from backend.app.services.stock_price_service import StockPriceService

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    db = Session(engine)
    service = ExternalKiwoomService(db)

    def item(stock_id: int, ready: bool, status_value: str) -> SupplyTopStockReturnTrendItem:
        return SupplyTopStockReturnTrendItem(
            rank=stock_id, stock_id=stock_id, stock_code=f"{stock_id:06d}", stock_name=f"종목{stock_id}",
            appearance_count=3, price_data_status=status_value, price_data_status_name=status_value,
            price_data_reason="test", has_sufficient_price_data=ready,
        )

    before_items = [item(1, True, "READY"), item(2, False, "NO_PRICE_DATA")]
    after_items = [item(1, True, "READY"), item(2, True, "READY")]

    def response(items, missing_ids, last_collection_date=None):
        return SupplyTopStockReturnTrendResponse(
            period_start_date="2026-06-27", period_end_date="2026-07-27", limit=20,
            last_price_collection_date=last_collection_date,
            price_readiness=SupplyTopStockPriceReadiness(
                total_stock_count=2, ready_stock_count=2 - len(missing_ids),
                missing_stock_count=len(missing_ids), readiness_rate=(2 - len(missing_ids)) * 50,
                missing_stock_ids=missing_ids, missing_stock_codes=[f"{value:06d}" for value in missing_ids],
            ),
            stocks=items,
        )

    responses = iter([response(before_items, [2]), response(after_items, [], "2026-07-27")])
    monkeypatch.setattr(service, "get_supply_top_stock_return_trend", lambda **_kwargs: next(responses))
    monkeypatch.setattr("backend.app.services.external_kiwoom_service.now_kst", lambda: "2026-07-27 12:00:00")
    captured = {}

    def refresh_only(_self, **kwargs):
        captured.update(kwargs)
        return [
            {
                "stock_id": 1, "stock_code": "000001", "stock_name": "종목1", "status": "SUCCESS",
                "collection_mode": "INCREMENTAL", "collect_start_date": "2026-07-24",
                "collect_end_date": "2026-07-27", "pages_fetched": 1, "collected_count": 2,
                "saved_count": 2, "error_message": None,
            },
            {
                "stock_id": 2, "stock_code": "000002", "stock_name": "종목2", "status": "SUCCESS",
                "collection_mode": "INITIAL", "collect_start_date": "2026-06-27",
                "collect_end_date": "2026-07-27", "pages_fetched": 1, "collected_count": 22,
                "saved_count": 22, "error_message": None,
            },
        ]

    monkeypatch.setattr(StockPriceService, "refresh_price_ranges_only", refresh_only)
    result = service.refresh_supply_top_stock_prices(SupplyTopStockPriceCollectRequest(
        period_start_date="2026-06-27", period_end_date="2026-07-27", limit=20,
    ))

    assert captured["stock_ids"] == [1, 2]
    assert captured["end_date"].isoformat() == "2026-07-27"
    assert captured["initial_lookback_days"] == 30
    assert result.target_stock_count == 2
    assert result.success_count == 2
    assert result.skipped_count == 0
    assert result.last_price_collection_date == "2026-07-27"
    assert {row.stock_id for row in result.results} == {1, 2}
    db.close()


def test_incremental_price_refresh_uses_per_stock_ranges_and_skips_derived(monkeypatch) -> None:
    from backend.app.services.stock_price_service import StockPriceService

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    db = Session(engine)
    service = StockPriceService(db)
    stocks = [
        SimpleNamespace(id=1, stock_code="000001", stock_name="최초종목"),
        SimpleNamespace(id=2, stock_code="000002", stock_name="기존종목"),
    ]
    monkeypatch.setattr(service.stock_repo, "get_by_ids", lambda _ids: stocks)
    monkeypatch.setattr(service.price_repo, "get_latest_trade_dates", lambda _ids: {2: "2026-07-24"})
    calls = []

    def collect_stats(stock, _source, start_date, end_date, **kwargs):
        calls.append((stock.id, start_date, end_date, kwargs))
        return {"normalized": stock.stock_code, "collected_count": 2, "saved_count": 2, "pages_fetched": 1}

    monkeypatch.setattr(service, "_collect_and_upsert_with_stats", collect_stats)
    result = service.refresh_price_ranges_only(
        stock_ids=[1, 2, 2], end_date=date(2026, 7, 27), initial_lookback_days=30,
    )

    assert [(stock_id, start.isoformat(), end.isoformat()) for stock_id, start, end, _ in calls] == [
        (1, "2026-06-27", "2026-07-27"),
        (2, "2026-07-24", "2026-07-27"),
    ]
    assert all(kwargs["recalculate_derived"] is False for *_, kwargs in calls)
    assert all(kwargs["stop_at_start_date"] is True for *_, kwargs in calls)
    assert all(kwargs["max_pages"] == 1 for *_, kwargs in calls)
    assert [row["collection_mode"] for row in result] == ["INITIAL", "INCREMENTAL"]
    db.close()
