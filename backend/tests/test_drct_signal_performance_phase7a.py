from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import event, text

from backend.app.services.drct_signal_performance_service import DrctSignalPerformanceService
from backend.tests.test_drct_marker_learning_phase6a import _db


def _seed_catalog(db) -> None:  # type: ignore[no-untyped-def]
    db.execute(text("INSERT INTO chart_marker_groups(id,name,color,sort_order,is_active,created_at,updated_at) VALUES(1,'지지','#16a34a',1,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
    for marker_id in (1, 2):
        db.execute(text("INSERT INTO chart_markers(id,marker_group_id,name,symbol,sort_order,is_active,created_at,updated_at) VALUES(:id,1,:name,:symbol,:id,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"), {"id": marker_id, "name": f"Marker {marker_id}", "symbol": str(marker_id)})
    for stock_id in (1, 2):
        db.execute(text("INSERT INTO stocks(id,stock_code,stock_name,is_active,created_at,updated_at) VALUES(:id,:code,:name,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"), {"id": stock_id, "code": f"00000{stock_id}", "name": f"종목{stock_id}"})
    db.commit()


def _price(db, stock_id: int, day: str, close: float, high: float | None = None, low: float | None = None) -> None:  # type: ignore[no-untyped-def]
    db.execute(text("""INSERT INTO stock_daily_prices
        (stock_id,trade_date,open_price,high_price,low_price,close_price,created_at,updated_at)
        VALUES(:stock,:day,:close,:high,:low,:close,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"""),
        {"stock": stock_id, "day": day, "close": close, "high": high if high is not None else close, "low": low if low is not None else close})


def _scan(day: str, pairs: list[tuple[int, int, bool]]) -> dict:  # type: ignore[type-arg]
    stocks: dict[int, dict] = {}
    for stock_id, marker_id, improvement in pairs:
        stock = stocks.setdefault(stock_id, {"stock_id": stock_id, "stock_code": f"00000{stock_id}", "stock_name": f"종목{stock_id}", "theme_names": [], "signals": []})
        stock["signals"].append({
            "marker_id": marker_id, "current_pattern_similarity": 71.25 + marker_id,
            "empirical_percentile": 82.5, "candidate_band": "HIGH_SIMILARITY",
            "improvement_candidate": improvement,
            "improvement_policy_version": "CANDIDATE_POLICY_SHADOW_V1",
        })
    return {"analysis_date": day, "stocks": list(stocks.values()), "_recording_metadata": {
        "improvement_pairs": [[stock_id, marker_id] for stock_id, marker_id, improvement in pairs if improvement],
        "improvement_policy_version": "CANDIDATE_POLICY_SHADOW_V1",
    }, "algorithm": {
        "candidate_policy_version": 1, "pattern_signature_version": 1,
        "similarity_algorithm_version": 1, "feature_schema_version": 1,
    }}


def test_signal_episode_is_idempotent_continues_closes_reenters_and_keeps_multi_marker() -> None:
    db = _db(); _seed_catalog(db)
    for day in ("2026-09-07", "2026-09-08", "2026-09-09", "2026-09-12"):
        _price(db, 1, day, 100)
    db.commit(); service = DrctSignalPerformanceService(db)

    first = service.capture(_scan("2026-09-07", [(1, 1, True), (1, 2, False)]))
    assert first == {"created": 2, "continued": 0, "closed": 0}
    assert service.capture(_scan("2026-09-07", [(1, 1, True), (1, 2, False)]))["created"] == 0
    assert service.capture(_scan("2026-09-08", [(1, 1, True), (1, 2, False)])) == {"created": 0, "continued": 2, "closed": 0}
    assert service.capture(_scan("2026-09-09", []))["closed"] == 2
    assert service.capture(_scan("2026-09-12", [(1, 1, False)]))["created"] == 1

    rows = db.execute(text("SELECT stock_id,marker_id,signal_date,last_seen_date,ended_date,improvement_candidate FROM drct_stock_signal_events ORDER BY id")).all()
    assert rows == [
        (1, 1, "2026-09-07", "2026-09-08", "2026-09-09", 1),
        (1, 2, "2026-09-07", "2026-09-08", "2026-09-09", 0),
        (1, 1, "2026-09-12", "2026-09-12", None, 0),
    ]


def test_performance_uses_exact_future_trading_rows_and_bulk_price_query() -> None:
    db = _db(); _seed_catalog(db)
    d0 = date(2026, 1, 2)
    _price(db, 1, d0.isoformat(), 100)
    _price(db, 2, d0.isoformat(), 200)
    business_days: list[date] = []
    cursor = d0
    while len(business_days) < 20:
        cursor += timedelta(days=1)
        if cursor.weekday() < 5 and cursor != date(2026, 1, 12):  # weekend and one market holiday omitted
            business_days.append(cursor)
    for index, day in enumerate(business_days, start=1):
        _price(db, 1, day.isoformat(), 100 + index, 105 + index, 96 + index)
        if index <= 7:
            _price(db, 2, day.isoformat(), 200 + index, 202 + index, 198 + index)
    db.commit(); service = DrctSignalPerformanceService(db)
    service.capture(_scan(d0.isoformat(), [(1, 1, True), (2, 1, False)]))

    price_selects = 0
    def count_prices(_conn, _cursor, statement, _parameters, _context, _executemany):  # type: ignore[no-untyped-def]
        nonlocal price_selects
        if statement.lstrip().upper().startswith("SELECT") and "FROM stock_daily_prices" in statement:
            price_selects += 1
    event.listen(db.get_bind(), "before_cursor_execute", count_prices)
    try:
        summary = service.refresh()
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", count_prices)

    complete = db.execute(text("SELECT * FROM drct_stock_signal_events WHERE stock_id=1")).mappings().one()
    partial = db.execute(text("SELECT * FROM drct_stock_signal_events WHERE stock_id=2")).mappings().one()
    assert price_selects == 1
    assert (complete["d5_date"], complete["d5_return_pct"]) == (business_days[4].isoformat(), 5.0)
    assert (complete["d10_date"], complete["d10_return_pct"]) == (business_days[9].isoformat(), 10.0)
    assert (complete["d20_date"], complete["d20_return_pct"]) == (business_days[19].isoformat(), 20.0)
    assert complete["max_rise_20_pct"] == 25.0 and complete["max_fall_20_pct"] == -3.0
    assert complete["evaluation_status"] == "COMPLETE"
    assert partial["evaluation_status"] == "D5_READY" and partial["d5_return_pct"] == 2.5
    assert partial["d10_return_pct"] is None and partial["max_rise_20_pct"] is None
    assert summary["total_count"] == 2 and summary["completed_count"] == 1 and summary["pending_count"] == 1


def test_event_storage_is_structured_and_has_no_reproducible_json_payload() -> None:
    db = _db()
    columns = {row[1] for row in db.execute(text("PRAGMA table_info(drct_stock_signal_events)")).all()}
    forbidden = {"feature_json", "scan_json", "chart_json", "signature_json", "similarity_vector", "search_result_json"}
    assert not columns.intersection(forbidden)


def test_performance_api_starts_empty_without_historical_backfill(isolated_api_client) -> None:  # type: ignore[no-untyped-def]
    summary = isolated_api_client.get("/drct-stock-signals/performance/summary")
    assert summary.status_code == 200
    assert summary.json()["total_count"] == 0
    refreshed = isolated_api_client.post("/drct-stock-signals/performance/refresh")
    assert refreshed.status_code == 200 and refreshed.json()["pending_count"] == 0
    events = isolated_api_client.get("/drct-stock-signals/performance/events")
    assert events.status_code == 200 and events.json() == {"total": 0, "items": []}


def test_operational_scan_rejects_historical_analysis_date(isolated_api_client) -> None:  # type: ignore[no-untyped-def]
    response = isolated_api_client.post(
        "/drct-stock-signals/marker-signals/scan-and-record",
        json={"analysis_date": "2026-09-04"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "운영 시그널 기록은 현재 기준일 스캔만 지원합니다."
