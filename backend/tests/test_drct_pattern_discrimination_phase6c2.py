from __future__ import annotations

from datetime import date

from sqlalchemy import text

from backend.app.services.marker_current_pattern_scan_service import MarkerCurrentPatternScanService
from backend.tests.test_drct_current_pattern_scan_phase6c import _seed_scan
from backend.tests.test_drct_marker_learning_phase6a import _db


def test_diagnostics_reuse_scan_distribution_and_keep_p25_policy() -> None:
    db = _db(); _seed_scan(db)
    service = MarkerCurrentPatternScanService(db)
    result = service.scan(date(2026, 6, 30))
    diagnostics = result["diagnostics"]
    marker = diagnostics["markers"][0]
    summary = result["marker_summaries"][0]

    assert service.query_count == 3  # requested date skips only the existing date-resolution query
    assert diagnostics["current_policy"] == "P25"
    assert diagnostics["storage_policy"] == "RUNTIME_ONLY"
    assert marker["training_s_count"] == marker["loo_evaluated_count"] == 5
    assert marker["loo_distribution"]["p25"] == summary["loo_p25"]
    assert marker["loo_distribution"]["median"] == summary["loo_median"]
    assert marker["loo_distribution"]["p75"] == summary["loo_p75"]
    for distribution in (marker["loo_distribution"], marker["current_distribution"]):
        assert distribution["min"] <= distribution["p10"] <= distribution["p25"]
        assert distribution["p25"] <= distribution["median"] <= distribution["p75"]
        assert distribution["p75"] <= distribution["p90"] <= distribution["max"]
    counts = [marker["thresholds"][key]["candidate_count"] for key in ("p25", "median", "p75", "p90")]
    assert counts == sorted(counts, reverse=True)
    assert marker["thresholds"]["p25"]["candidate_count"] == summary["candidate_count"]
    assert diagnostics["policies"]["p25"]["candidate_pair_count"] == result["candidate_pair_count"]
    assert diagnostics["policies"]["p25"]["candidate_stock_count"] == result["candidate_stock_count"]
    assert marker["thresholds"]["p25"]["candidate_ratio"] == counts[0] / marker["current_evaluable_count"] * 100


def test_diagnostics_stock_dedupe_multiple_markers_and_no_n_plus_one() -> None:
    db = _db(); _seed_scan(db)
    db.execute(text("INSERT INTO chart_markers(id,marker_group_id,name,symbol,sort_order,is_active,created_at,updated_at) VALUES(2,1,'지지 - 두 번째 Marker','2',2,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
    for stock_id in range(1, 6):
        db.execute(text("INSERT INTO chart_marker_events(id,stock_id,marker_id,marker_date,review_result,created_at,updated_at) VALUES(:id,:stock,2,'2026-05-01','S',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"), {"id": 100 + stock_id, "stock": stock_id})
    db.commit()
    service = MarkerCurrentPatternScanService(db)
    result = service.scan(date(2026, 5, 1))
    policy = result["diagnostics"]["policies"]["p25"]

    assert service.query_count == 3  # diagnostics add no query to the dated scan
    assert result["eligible_marker_count"] == 2
    assert policy["candidate_pair_count"] >= policy["candidate_stock_count"]
    assert policy["multiple_marker_stock_count"] > 0


def test_diagnostics_ignore_failure_outcome_and_do_not_write() -> None:
    db = _db(); _seed_scan(db)
    tables = ("chart_marker_events", "chart_marker_learning_decisions", "drct_signal_searches")
    before_counts = {table: db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one() for table in tables}
    before = MarkerCurrentPatternScanService(db).scan(date(2026, 6, 30))["diagnostics"]
    db.execute(text("INSERT INTO chart_marker_events(id,stock_id,marker_id,marker_date,review_result,created_at,updated_at) VALUES(90,7,1,'2026-05-15','F',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
    db.commit()
    after = MarkerCurrentPatternScanService(db).scan(date(2026, 6, 30))["diagnostics"]

    assert before == after
    assert {table: db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one() for table in tables} == before_counts | {"chart_marker_events": before_counts["chart_marker_events"] + 1}
    payload_text = str(after).lower()
    assert "outcome" not in payload_text and "search" not in payload_text
    assert "similarity_vector" not in payload_text


def test_detail_supports_runtime_review_below_current_candidate() -> None:
    db = _db(); _seed_scan(db)
    db.execute(text("UPDATE stock_daily_prices SET close_price=99999,high_price=100000,low_price=99998 WHERE stock_id=7 AND trade_date='2026-06-30'"))
    db.commit()
    scan = MarkerCurrentPatternScanService(db).scan(date(2026, 6, 30))
    candidate_ids = {stock["stock_id"] for stock in scan["stocks"]}
    detail = MarkerCurrentPatternScanService(db).detail(7, 1, date(2026, 6, 30))

    assert 7 not in candidate_ids
    assert detail["signal"]["candidate_band"] == "BELOW_CANDIDATE"
    assert detail["storage_policy"] == "RUNTIME_ONLY"
