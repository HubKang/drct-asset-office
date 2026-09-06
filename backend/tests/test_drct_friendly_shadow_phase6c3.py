from __future__ import annotations

from datetime import date

from sqlalchemy import text

from backend.app.services.marker_candidate_policy_research_service import (
    BASELINE_POLICY_VERSION,
    CANDIDATE_RANGE_RATIO_LIMITS,
    SHADOW_POLICY_VERSION,
    MarkerCandidatePolicyResearchService,
)
from backend.app.services.marker_current_pattern_scan_service import MarkerCurrentPatternScanService
from backend.tests.test_drct_current_pattern_scan_phase6c import _seed_scan
from backend.tests.test_drct_marker_learning_phase6a import _db


def _scan_marker(db):  # type: ignore[no-untyped-def]
    result = MarkerCurrentPatternScanService(db).scan(date(2026, 6, 30))
    return result, result["diagnostics"]["markers"][0]


def test_friendly_policy_keeps_baseline_and_builds_deterministic_shadow() -> None:
    db = _db(); _seed_scan(db)
    first, marker = _scan_marker(db)
    second, marker_again = _scan_marker(db)

    assert first["candidate_stock_count"] == first["diagnostics"]["policies"]["p25"]["candidate_stock_count"]
    assert first["diagnostics"]["baseline_policy_version"] == BASELINE_POLICY_VERSION
    assert first["diagnostics"]["shadow_policy_version"] == SHADOW_POLICY_VERSION
    assert first["diagnostics"]["shadow_policy_status"] == "VALIDATING"
    assert marker["friendly"] == marker_again["friendly"]
    assert marker["friendly"]["shadow"]["similarity_threshold"] == max(
        marker["loo_distribution"]["p25"], marker["current_distribution"]["p90"],
    )
    assert marker["friendly"]["shadow"]["candidate_count"] <= marker["friendly"]["current_candidate_count"]
    assert marker["friendly"]["shadow"]["policy_version"] == SHADOW_POLICY_VERSION
    assert first["storage_policy"] == first["diagnostics"]["storage_policy"] == "RUNTIME_ONLY"
    assert second["candidate_stock_count"] == first["candidate_stock_count"]


def test_candidate_range_and_discrimination_status_boundaries() -> None:
    status = MarkerCandidatePolicyResearchService._range_status
    assert status(CANDIDATE_RANGE_RATIO_LIMITS["NARROW"]) == "NARROW"
    assert status(CANDIDATE_RANGE_RATIO_LIMITS["NARROW"] + 0.1) == "MODERATE"
    assert status(CANDIDATE_RANGE_RATIO_LIMITS["MODERATE"] + 0.1) == "BROAD"
    assert status(CANDIDATE_RANGE_RATIO_LIMITS["BROAD"] + 0.1) == "VERY_BROAD"
    discrimination = MarkerCandidatePolicyResearchService._discrimination_status
    assert discrimination({"median": 60, "p75": 70}, {"median": 40, "p75": 50}) == "GOOD"
    assert discrimination({"median": 44, "p75": 70}, {"median": 40, "p75": 68}) == "WEAK"
    assert discrimination({"median": 40, "p75": 70}, {"median": 50, "p75": 60}) == "REVIEW"


def test_new_success_case_recalculates_signature_levels_and_shadow_without_button() -> None:
    db = _db(); _seed_scan(db)
    before, before_marker = _scan_marker(db)
    db.execute(text("""
        INSERT INTO chart_marker_events(
            id,stock_id,marker_id,marker_date,review_result,created_at,updated_at
        ) VALUES(70,7,1,'2026-05-15','S',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)
    """))
    db.commit()
    after, after_marker = _scan_marker(db)

    assert before_marker["training_s_count"] == 5
    assert after_marker["training_s_count"] == 6
    assert after_marker["loo_distribution"] != before_marker["loo_distribution"]
    assert after_marker["friendly"]["reference_levels"] != before_marker["friendly"]["reference_levels"]
    assert after_marker["friendly"]["shadow"] != before_marker["friendly"]["shadow"]
    assert after["candidate_stock_count"] == after["diagnostics"]["policies"]["p25"]["candidate_stock_count"]
    assert before["timings"]["sql_query_count"] == after["timings"]["sql_query_count"] == 3


def test_manual_exclude_is_reflected_and_research_remains_read_only() -> None:
    db = _db(); _seed_scan(db)
    before, before_marker = _scan_marker(db)
    before_decisions = db.execute(text("SELECT COUNT(*) FROM chart_marker_learning_decisions")).scalar_one()
    db.execute(text("""
        INSERT INTO chart_marker_events(
            id,stock_id,marker_id,marker_date,review_result,created_at,updated_at
        ) VALUES(70,7,1,'2026-05-15','S',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)
    """))
    db.execute(text("""
        INSERT INTO chart_marker_learning_decisions(
            chart_marker_event_id,decision,decision_reason,pattern_algorithm_version,created_at,updated_at
        ) VALUES(70,'EXCLUDE','manual review',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)
    """))
    db.commit()
    after, after_marker = _scan_marker(db)

    assert after_marker == before_marker
    assert after["candidate_stock_count"] == before["candidate_stock_count"]
    assert db.execute(text("SELECT COUNT(*) FROM chart_marker_learning_decisions")).scalar_one() == before_decisions + 1


def test_shadow_is_independent_of_search_failure_and_outcome_data() -> None:
    db = _db(); _seed_scan(db)
    before, _ = _scan_marker(db)
    before_shadow = before["diagnostics"]["shadow_policy"]
    db.execute(text("""
        INSERT INTO chart_marker_events(
            id,stock_id,marker_id,marker_date,review_result,created_at,updated_at
        ) VALUES(80,7,1,'2026-05-20','F',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)
    """))
    db.commit()
    after, _ = _scan_marker(db)

    assert after["diagnostics"]["shadow_policy"] == before_shadow
    payload = str(after["diagnostics"]).lower()
    assert "search" not in payload and "outcome" not in payload
