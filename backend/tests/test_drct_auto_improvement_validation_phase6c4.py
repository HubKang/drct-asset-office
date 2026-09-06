from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import text

from backend.app.services.marker_candidate_policy_validation_service import (
    MarkerCandidatePolicyValidationService,
)
from backend.app.services.marker_current_pattern_scan_service import MarkerCurrentPatternScanService
from backend.app.services.marker_pattern_signature_service import MarkerPatternSignatureService
from backend.tests.test_drct_current_pattern_scan_phase6c import _seed_scan
from backend.tests.test_drct_marker_learning_phase6a import _db


def _seed_ordered_replay(db):  # type: ignore[no-untyped-def]
    _seed_scan(db)
    dates = ("2026-04-05", "2026-04-15", "2026-04-25", "2026-05-05", "2026-05-15")
    for event_id, d0 in enumerate(dates, start=1):
        db.execute(text("UPDATE chart_marker_events SET marker_date=:d0 WHERE id=:event_id"), {"d0": d0, "event_id": event_id})
    db.execute(text("""
        INSERT INTO chart_marker_events(id,stock_id,marker_id,marker_date,review_result,created_at,updated_at)
        VALUES(70,7,1,'2026-06-01','S',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)
    """))
    db.commit()


def _clear_cache() -> None:
    with MarkerCandidatePolicyValidationService._cache_lock:
        MarkerCandidatePolicyValidationService._cache.clear()


def test_replay_orders_targets_and_uses_prior_successes_only(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_cache(); db = _db(); _seed_ordered_replay(db)
    original = MarkerPatternSignatureService.build_signature
    observed: list[tuple[str, ...]] = []

    def capture(cases, profile):  # type: ignore[no-untyped-def]
        observed.append(tuple(str(case["d0"]) for case in cases))
        return original(cases, profile)

    monkeypatch.setattr(MarkerPatternSignatureService, "build_signature", capture)
    result = MarkerCandidatePolicyValidationService(db).validate(1, date(2026, 6, 30))

    assert [row["d0"] for row in result["targets"]] == ["2026-05-05", "2026-05-15", "2026-06-01"]
    for target in result["targets"]:
        assert target["prior_case_count"] >= 3
        assert all(d0 < target["d0"] for d0 in next(group for group in observed if len(group) == target["prior_case_count"]))
    assert result["historical_valid_target_count"] == 3
    assert result["formal_target_count"] == 1


def test_replay_excludes_future_prices_events_and_target_itself() -> None:
    _clear_cache(); db = _db(); _seed_ordered_replay(db)
    before = MarkerCandidatePolicyValidationService(db).validate(1, date(2026, 6, 30))
    db.execute(text("UPDATE stock_daily_prices SET close_price=99999,high_price=100000,low_price=99998,updated_at='future' WHERE trade_date>'2026-06-30'"))
    db.execute(text("""
        INSERT INTO chart_marker_events(id,stock_id,marker_id,marker_date,review_result,created_at,updated_at)
        VALUES(71,7,1,'2026-07-01','S',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)
    """))
    db.commit(); _clear_cache()
    after = MarkerCandidatePolicyValidationService(db).validate(1, date(2026, 6, 30))

    comparable = ("training_s_count", "historical_valid_target_count", "baseline_hit_count",
                  "improvement_hit_count", "baseline_average_candidate_count", "improvement_average_candidate_count")
    assert {key: before[key] for key in comparable} == {key: after[key] for key in comparable}
    assert all(row["prior_case_count"] < before["training_s_count"] for row in before["targets"])


def test_manual_exclude_and_core_readiness_change_validation_without_writes() -> None:
    _clear_cache(); db = _db(); _seed_ordered_replay(db)
    before_counts = {table: db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one() for table in (
        "chart_marker_events", "chart_marker_learning_decisions", "drct_signal_searches",
    )}
    before = MarkerCandidatePolicyValidationService(db).validate(1, date(2026, 6, 30))
    assert {table: db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one() for table in before_counts} == before_counts

    db.execute(text("""
        INSERT INTO chart_marker_learning_decisions(
            chart_marker_event_id,decision,decision_reason,pattern_algorithm_version,created_at,updated_at
        ) VALUES(70,'EXCLUDE','manual',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)
    """)); db.commit(); _clear_cache()
    excluded = MarkerCandidatePolicyValidationService(db).validate(1, date(2026, 6, 30))
    assert excluded["training_s_count"] == before["training_s_count"] - 1
    assert excluded["historical_valid_target_count"] == before["historical_valid_target_count"] - 1

    db.execute(text("DELETE FROM chart_marker_learning_decisions WHERE chart_marker_event_id=70"))
    db.execute(text("DELETE FROM stock_daily_prices WHERE stock_id=7 AND trade_date<='2026-06-01'")); db.commit(); _clear_cache()
    incomplete = MarkerCandidatePolicyValidationService(db).validate(1, date(2026, 6, 30))
    assert incomplete["training_s_count"] == excluded["training_s_count"]


def test_status_gate_covers_all_four_user_states() -> None:
    status = MarkerCandidatePolicyValidationService.improvement_status
    assert status(2, 2, 2, 60, 18) == "NEED_MORE_DATA"
    assert status(3, 2, 2, 60, 18) == "VALIDATING"
    assert status(3, 3, 3, 60, 18) == "IMPROVEMENT_READY"
    assert status(3, 3, 2, 60, 18) == "KEEP_CURRENT"
    assert status(3, 3, 3, 60, 55) == "VALIDATING"


def test_replay_is_runtime_cached_and_does_not_change_current_scan(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_cache(); db = _db(); _seed_ordered_replay(db)
    current_before = MarkerCurrentPatternScanService(db).scan_summary(date(2026, 6, 30))
    first = MarkerCandidatePolicyValidationService(db).validate(1, date(2026, 6, 30))
    service = MarkerCandidatePolicyValidationService(db)
    monkeypatch.setattr(service, "_prices", lambda *_args: pytest.fail("warm replay must use request-memory cache"))
    second = service.validate(1, date(2026, 6, 30))
    current_after = MarkerCurrentPatternScanService(db).scan_summary(date(2026, 6, 30))

    assert second["timings"]["cache_hit"] is True
    assert first["targets"] == second["targets"]
    assert current_after["stocks"] == current_before["stocks"]
    assert current_after["candidate_stock_count"] == current_before["candidate_stock_count"]
    assert first["storage_policy"] == "RUNTIME_ONLY"
    payload = str(first).lower()
    assert "outcome" not in payload and "search" not in payload
