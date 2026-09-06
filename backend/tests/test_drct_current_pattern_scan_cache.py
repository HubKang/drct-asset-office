from __future__ import annotations

from datetime import date

from sqlalchemy import text

from backend.app.services.marker_current_pattern_scan_service import MarkerCurrentPatternScanService
from backend.tests.test_drct_current_pattern_scan_phase6c import _seed_scan
from backend.tests.test_drct_marker_learning_phase6a import _db


def _clear_signature_cache() -> None:
    with MarkerCurrentPatternScanService._signature_cache_lock:
        MarkerCurrentPatternScanService._signature_cache.clear()


def test_summary_omits_diagnostics_and_reuses_runtime_signature_cache() -> None:
    _clear_signature_cache()
    db = _db(); _seed_scan(db)
    first = MarkerCurrentPatternScanService(db).scan_summary(date(2026, 6, 30))

    assert "diagnostics" not in first
    assert first["eligible_marker_count"] == 1

    service = MarkerCurrentPatternScanService(db)
    service._bulk_prices = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("cache miss"))  # type: ignore[method-assign]
    second = service.scan_summary(date(2026, 6, 30))

    assert second["candidate_stock_count"] == first["candidate_stock_count"]
    assert second["marker_summaries"] == first["marker_summaries"]
    assert second["timings"]["sql_query_count"] == 3


def test_diagnostics_are_loaded_separately_from_cached_signature() -> None:
    _clear_signature_cache()
    db = _db(); _seed_scan(db)
    MarkerCurrentPatternScanService(db).scan_summary(date(2026, 6, 30))

    diagnostics = MarkerCurrentPatternScanService(db).diagnostics(date(2026, 6, 30))

    assert diagnostics["current_policy"] == "P25"
    assert diagnostics["markers"]
    assert diagnostics["storage_policy"] == "RUNTIME_ONLY"


def test_new_success_event_invalidates_signature_cache_immediately() -> None:
    _clear_signature_cache()
    db = _db(); _seed_scan(db)
    before = MarkerCurrentPatternScanService(db).scan_summary(date(2026, 6, 30))
    db.execute(text("""
        INSERT INTO chart_marker_events(
            id,stock_id,marker_id,marker_date,review_result,created_at,updated_at
        ) VALUES(70,7,1,'2026-05-15','S',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)
    """))
    db.commit()

    after = MarkerCurrentPatternScanService(db).scan_summary(date(2026, 6, 30))

    assert before["marker_summaries"][0]["training_case_count"] == 5
    assert after["marker_summaries"][0]["training_case_count"] == 6
