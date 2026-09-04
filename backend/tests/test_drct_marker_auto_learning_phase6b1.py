from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from backend.app.services.marker_auto_learning_service import MarkerAutoLearningService
from backend.app.services.marker_pattern_signature_service import MarkerPatternSignatureService
from backend.app.services.marker_training_case_service import MarkerDatasetBuild, MarkerTrainingCaseService
from backend.tests.test_drct_marker_learning_phase6a import _db, _seed
from backend.tests.test_drct_marker_pattern_phase6b import _case


def _build(values: list[float]) -> MarkerDatasetBuild:
    cases = []
    for event_id, value in enumerate(values, 1):
        case = _case(event_id, value, "S")
        case.update({"marker_id": 1, "marker_name": "테스트", "learning_decision": None})
        cases.append(case)
    return MarkerDatasetBuild(
        marker={"marker_id": 1, "marker_name": "테스트"},
        cases=cases,
        related_search_count=0,
        elapsed_ms=0,
    )


def test_review_queue_requires_five_ready_success_cases() -> None:
    rows, threshold = MarkerAutoLearningService._review_rows(_build([0, .1, .2, 100]))
    assert rows == [] and threshold is None
    rows, threshold = MarkerAutoLearningService._review_rows(_build([0, .1, .2, .3, 100]))
    assert threshold is not None
    assert [row["chart_marker_event_id"] for row in rows] == [5]


def test_include_removes_review_recommendation_but_keeps_primary_learning() -> None:
    build = _build([0, .1, .2, .3, 100])
    build.cases[-1]["learning_decision"] = "INCLUDE"
    rows, _ = MarkerAutoLearningService._review_rows(build)
    assert rows == []
    assert MarkerPatternSignatureService.build_signature(build.cases, "CORE")["case_count"] == 5


def test_exclude_removes_case_from_primary_signature() -> None:
    build = _build([0, .1, .2, .3, 100])
    build.cases[-1]["learning_decision"] = "EXCLUDE"
    assert MarkerPatternSignatureService.build_signature(build.cases, "CORE")["case_count"] == 4


def test_decision_upsert_persists_only_explicit_curator_fields() -> None:
    db = _db(); marker_id = _seed(db); service = MarkerAutoLearningService(db)
    first = service.decide(marker_id, 1, "EXCLUDE", "패턴 예외")
    second = service.decide(marker_id, 1, "INCLUDE", "정상 변형")
    assert first["decision"] == "EXCLUDE" and second["decision"] == "INCLUDE"
    assert db.execute(text("SELECT COUNT(*) FROM chart_marker_learning_decisions")).scalar_one() == 1
    columns = {row[1] for row in db.execute(text("PRAGMA table_info(chart_marker_learning_decisions)")).all()}
    assert not {"similarity", "features", "signature", "loo", "outlier"}.intersection(columns)
    build = MarkerTrainingCaseService(db).build(marker_id)
    assert build.cases[0]["learning_decision"] == "INCLUDE"


def test_failure_case_cannot_receive_learning_decision() -> None:
    db = _db(); marker_id = _seed(db)
    with pytest.raises(HTTPException) as error:
        MarkerAutoLearningService(db).decide(marker_id, 2, "EXCLUDE", None)
    assert error.value.status_code == 409


def test_bulk_catalog_returns_card_status_without_per_marker_price_queries(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    db = _db(); _seed(db); service = MarkerAutoLearningService(db)
    calls = {"prices": 0, "indicators": 0}
    original_prices, original_indicators = service.training._prices, service.training._indicators

    def prices(stock_ids):  # type: ignore[no-untyped-def]
        calls["prices"] += 1
        return original_prices(stock_ids)

    def indicators(stock_ids):  # type: ignore[no-untyped-def]
        calls["indicators"] += 1
        return original_indicators(stock_ids)

    monkeypatch.setattr(service.training, "_prices", prices)
    monkeypatch.setattr(service.training, "_indicators", indicators)
    result = service.catalog()
    assert calls == {"prices": 1, "indicators": 1}
    assert result["items"][0]["learning_case_count"] == 1
    assert result["items"][0]["review_recommended_count"] == 0
    assert result["items"][0]["learning_status"] == "INSUFFICIENT"


@pytest.mark.parametrize("count,learning,recommendation", [
    (0, "INSUFFICIENT", "INSUFFICIENT"), (2, "INSUFFICIENT", "INSUFFICIENT"),
    (3, "EARLY", "RESEARCH"), (4, "EARLY", "RESEARCH"), (5, "TESTABLE", "READY"),
])
def test_status_boundaries(count: int, learning: str, recommendation: str) -> None:
    assert MarkerAutoLearningService._status(count) == (learning, recommendation)
