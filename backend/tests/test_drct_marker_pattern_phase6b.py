from __future__ import annotations

from copy import deepcopy

import pytest
from sqlalchemy import text

from backend.app.services.drct_pattern_feature_service import CORE_FEATURE_NAMES, ENRICHED_FEATURE_NAMES
from backend.app.services.marker_pattern_signature_service import (
    DISTANCE_CAP,
    MarkerPatternSignatureService,
)
from backend.app.services.marker_training_case_service import MarkerTrainingCaseService
from backend.app.schemas.drct_marker_learning_schema import (
    MarkerPatternSignatureResponse, MarkerSimilarityCaseDetailResponse, MarkerSimilarityValidationResponse,
)
from backend.tests.test_drct_marker_learning_phase6a import _db, _seed


def _case(event_id: int, value: float, review_result: str | None = "S") -> dict:
    core = {name: value + index * 0.01 for index, name in enumerate(CORE_FEATURE_NAMES)}
    enriched = {**core, **{name: value + index * 0.02 for index, name in enumerate(ENRICHED_FEATURE_NAMES[16:])}}
    return {
        "chart_marker_event_id": event_id, "stock_id": event_id, "stock_code": f"{event_id:06d}",
        "stock_name": f"종목{event_id}", "d0": f"2026-01-{event_id:02d}", "review_result": review_result,
        "core_status": "READY", "enriched_status": "READY", "core_features": core,
        "enriched_features": enriched, "outcomes": {"d20_return": value * 1000},
    }


def test_signature_uses_robust_statistics_and_status_boundaries() -> None:
    cases = [_case(1, 0), _case(2, 1), _case(3, 2), _case(4, 100), _case(5, 3)]
    result = MarkerPatternSignatureService.build_signature(cases, "CORE")
    first = result["features"][0]
    assert result["status"] == "TESTABLE" and result["case_count"] == 5
    assert first["median"] == 2 and first["q1"] == 1 and first["q3"] == 3
    assert first["iqr"] == 2 and first["mad"] == 1 and first["scale_method"] == "IQR"
    assert MarkerPatternSignatureService.learning_status(2) == "INSUFFICIENT"
    assert MarkerPatternSignatureService.learning_status(3) == "EXPERIMENTAL"
    assert MarkerPatternSignatureService.learning_status(5) == "TESTABLE"


def test_constant_features_are_visible_but_excluded_from_distance() -> None:
    cases = [_case(index, 7) for index in range(1, 6)]
    signature = MarkerPatternSignatureService.build_signature(cases, "CORE")
    assert signature["constant_feature_count"] == len(CORE_FEATURE_NAMES)
    assert all(feature["status"] == "CONSTANT" and feature["robust_scale"] is None for feature in signature["features"])
    assert MarkerPatternSignatureService.score(cases[0]["core_features"], signature) is None


def test_robust_scale_falls_back_to_mad_without_arbitrary_unit_scale() -> None:
    assert MarkerPatternSignatureService.robust_scale(2.0, 9.0) == (2.0, "IQR", "ACTIVE")
    scale, method, status = MarkerPatternSignatureService.robust_scale(0.0, 2.0)
    assert scale == pytest.approx(2.9652) and method == "MAD" and status == "ACTIVE"
    assert MarkerPatternSignatureService.robust_scale(0.0, 0.0) == (None, "NONE", "CONSTANT")


def test_distance_is_equal_weight_median_capped_and_similarity_is_not_probability() -> None:
    signature = {
        "constant_feature_count": 1,
        "features": [
            {"key": "a", "label": "A", "unit": "", "median": 0.0, "robust_scale": 2.0, "status": "ACTIVE"},
            {"key": "b", "label": "B", "unit": "", "median": 0.0, "robust_scale": 1.0, "status": "ACTIVE"},
            {"key": "c", "label": "C", "unit": "", "median": 1.0, "robust_scale": None, "status": "CONSTANT"},
        ],
    }
    exact = MarkerPatternSignatureService.score({"a": 0, "b": 0, "c": 99}, signature)
    distant = MarkerPatternSignatureService.score({"a": 2, "b": 99, "c": -99}, signature)
    assert exact and exact["pattern_distance"] == 0 and exact["pattern_similarity"] == 100
    assert distant and distant["pattern_distance"] == 2
    assert distant["pattern_similarity"] == pytest.approx(100 / 3)
    assert distant["feature_distances"][0]["robust_distance"] == DISTANCE_CAP


def test_loo_excludes_self_and_ignores_outcome_and_search_metadata() -> None:
    cases = [_case(1, 0), _case(2, 1), _case(3, 2), _case(4, 3), _case(5, 100)]
    baseline = MarkerPatternSignatureService.validate(cases, "CORE")
    changed = deepcopy(cases)
    for case in changed:
        case["outcomes"] = {"d20_return": -999999}
        case["search_id"] = 999
        case["rule_status"] = "NO_MATCH"
    changed_result = MarkerPatternSignatureService.validate(changed, "CORE")
    assert changed_result["distribution"] == baseline["distribution"]
    assert [(row["chart_marker_event_id"], row["pattern_distance"], row["pattern_similarity"])
            for row in changed_result["cases"]] == [
                (row["chart_marker_event_id"], row["pattern_distance"], row["pattern_similarity"])
                for row in baseline["cases"]
            ]
    outlier = next(row for row in baseline["cases"] if row["chart_marker_event_id"] == 5)
    full_signature = MarkerPatternSignatureService.build_signature(cases, "CORE")
    loo_signature = MarkerPatternSignatureService.build_signature(cases[:-1], "CORE")
    assert loo_signature["features"][0]["median"] == 1.5
    assert full_signature["features"][0]["median"] == 2
    assert outlier["pattern_distance"] == DISTANCE_CAP
    assert baseline["evaluated_count"] == 5 and baseline["distribution"] is not None


def test_core_and_enriched_are_separate_and_missing_enriched_is_excluded() -> None:
    cases = [_case(index, float(index)) for index in range(1, 6)]
    cases[0]["enriched_status"] = "ENRICHED_DATA_INCOMPLETE"
    cases[0]["enriched_features"] = None
    core = MarkerPatternSignatureService.build_signature(cases, "CORE")
    enriched = MarkerPatternSignatureService.build_signature(cases, "ENRICHED")
    assert core["case_count"] == 5 and len(core["features"]) == 16
    assert enriched["case_count"] == 4 and len(enriched["features"]) == 20
    assert enriched["status"] == "EXPERIMENTAL"


def test_runtime_signature_does_not_write_to_database() -> None:
    db = _db(); marker_id = _seed(db)
    service = MarkerTrainingCaseService(db)
    before = {table: db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
              for table in ("chart_marker_events", "stock_daily_prices", "drct_signal_searches")}
    build = service.build(marker_id)
    signature = MarkerPatternSignatureService.signature_response(build, "CORE")
    validation = MarkerPatternSignatureService.validation_response(build, "CORE")
    detail = MarkerPatternSignatureService.case_detail(build, 1, "CORE")
    after = {table: db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one() for table in before}
    assert signature["storage_policy"] == "RUNTIME_ONLY"
    assert signature["case_count"] == 1
    assert validation["evaluated_count"] == 0 and validation["storage_policy"] == "RUNTIME_ONLY"
    MarkerPatternSignatureResponse.model_validate(signature)
    MarkerSimilarityValidationResponse.model_validate(validation)
    assert detail is None
    assert before == after


def test_primary_signature_uses_only_ready_success_not_excluded_cases() -> None:
    cases = [_case(1, 1, "S"), _case(2, 2, "F"), _case(3, 3, None), _case(4, 4, "S")]
    cases[3]["learning_decision"] = "EXCLUDE"
    signature = MarkerPatternSignatureService.build_signature(cases, "CORE")
    assert signature["case_count"] == 1
    assert signature["features"][0]["median"] == 1
