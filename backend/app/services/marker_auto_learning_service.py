from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.services.marker_pattern_signature_service import (
    PATTERN_SIMILARITY_ALGORITHM_VERSION,
    MarkerPatternSignatureService,
)
from backend.app.services.marker_training_case_service import MarkerDatasetBuild, MarkerTrainingCaseService
from backend.app.services.marker_review_result import normalize_marker_review_result


class MarkerAutoLearningService:
    """S-only, runtime marker learning summary and curator review decisions."""

    def __init__(self, db: Session):
        self.db = db
        self.training = MarkerTrainingCaseService(db)

    def catalog(self) -> dict[str, Any]:
        """Return one compact bulk payload for the accordion without per-marker API calls."""
        markers = self.training.catalog()["items"]
        if not markers:
            return {"items": []}
        rows = self.db.execute(text("""
            SELECT event.id chart_marker_event_id, event.marker_id, event.stock_id,
                   event.marker_date d0, event.review_result, stock.stock_code, stock.stock_name,
                   decision.decision learning_decision, decision.decision_reason,
                   decision.updated_at decision_updated_at
            FROM chart_marker_events event
            JOIN chart_markers marker ON marker.id=event.marker_id AND marker.is_active=1
            JOIN chart_marker_groups marker_group ON marker_group.id=marker.marker_group_id AND marker_group.is_active=1
            JOIN stocks stock ON stock.id=event.stock_id
            LEFT JOIN chart_marker_learning_decisions decision ON decision.chart_marker_event_id=event.id
            ORDER BY marker_group.sort_order, marker.sort_order, event.marker_date, event.id
        """)).mappings().all()
        events_by_marker: dict[int, list[dict[str, Any]]] = {}
        stock_ids: set[int] = set()
        for raw in rows:
            event = dict(raw)
            event["review_result"] = normalize_marker_review_result(event.get("review_result"))
            marker_id = int(event["marker_id"])
            events_by_marker.setdefault(marker_id, []).append(event)
            stock_ids.add(int(event["stock_id"]))
        prices = self.training._prices(sorted(stock_ids))
        indicators = self.training._indicators(sorted(stock_ids))
        items = []
        for marker in markers:
            marker_id = int(marker["marker_id"])
            cases = self.training._cases_from_events(marker, events_by_marker.get(marker_id, []), prices, indicators)
            build = MarkerDatasetBuild(marker=marker, cases=cases, related_search_count=0, elapsed_ms=0)
            learning_count = len(MarkerPatternSignatureService._eligible(cases, "CORE"))
            review_rows, _ = self._review_rows(build)
            learning_status, _ = self._status(learning_count)
            items.append({
                **marker,
                "learning_case_count": learning_count,
                "review_recommended_count": len(review_rows),
                "learning_status": learning_status,
            })
        return {"items": items}

    @staticmethod
    def _status(count: int) -> tuple[str, str]:
        if count < 3:
            return "INSUFFICIENT", "INSUFFICIENT"
        if count < 5:
            return "EARLY", "RESEARCH"
        return "TESTABLE", "READY"

    @staticmethod
    def _validation(build: MarkerDatasetBuild) -> dict[str, Any]:
        return MarkerPatternSignatureService.validate(build.cases, "CORE")

    @classmethod
    def _review_rows(cls, build: MarkerDatasetBuild) -> tuple[list[dict[str, Any]], float | None]:
        validation = cls._validation(build)
        rows = validation["cases"]
        if len(rows) < 5:
            return [], None
        distances = np.asarray([float(row["pattern_distance"]) for row in rows], dtype=float)
        q1 = float(np.percentile(distances, 25, method="linear"))
        q3 = float(np.percentile(distances, 75, method="linear"))
        threshold = q3 + 1.5 * (q3 - q1)
        cases_by_id = {int(case["chart_marker_event_id"]): case for case in build.cases}
        review_rows = []
        for row in rows:
            case = cases_by_id[int(row["chart_marker_event_id"])]
            if case.get("learning_decision") is not None or float(row["pattern_distance"]) <= threshold:
                continue
            review_rows.append({
                **row,
                "marker_id": int(case["marker_id"]),
                "marker_name": str(case["marker_name"]),
                "reason": "성공 학습 사례의 일반 범위에서 벗어난 패턴입니다.",
                "outlier_threshold": threshold,
                "learning_decision": None,
            })
        return sorted(review_rows, key=lambda row: (-row["pattern_distance"], row["d0"])), threshold

    def summary(self, marker_id: int) -> dict[str, Any]:
        build = self.training.build(marker_id)
        eligible = MarkerPatternSignatureService._eligible(build.cases, "CORE")
        review_rows, _ = self._review_rows(build)
        validation = self._validation(build)
        distribution = validation.get("distribution")
        status, recommendation = self._status(len(eligible))
        success_cases = [case for case in build.cases if case.get("review_result") == "S"]
        return {
            "marker": build.marker,
            "success_count": len(success_cases),
            "learning_case_count": len(eligible),
            "manual_excluded_count": sum(case.get("review_result") == "S" and case.get("learning_decision") == "EXCLUDE" for case in build.cases),
            "data_incomplete_count": sum(case.get("review_result") == "S" and case.get("core_status") != "READY" for case in build.cases),
            "review_recommended_count": len(review_rows),
            "learning_status": status,
            "recommendation_readiness": recommendation,
            "consistency_median": distribution.get("median") if distribution else None,
            "consistency_p25": distribution.get("p25") if distribution else None,
            "consistency_p75": distribution.get("p75") if distribution else None,
            "latest_d0": max((case["d0"] for case in success_cases), default=None),
            "calculated_at": datetime.now().isoformat(timespec="seconds"),
            "pattern_algorithm_version": PATTERN_SIMILARITY_ALGORITHM_VERSION,
        }

    def review_cases(self, marker_id: int) -> dict[str, Any]:
        build = self.training.build(marker_id)
        rows, threshold = self._review_rows(build)
        return {"marker_id": marker_id, "total": len(rows), "outlier_threshold": threshold, "items": rows}

    def review_case(self, marker_id: int, event_id: int) -> dict[str, Any]:
        build = self.training.build(marker_id)
        rows, threshold = self._review_rows(build)
        row = next((item for item in rows if int(item["chart_marker_event_id"]) == event_id), None)
        if row is None:
            raise HTTPException(404, "현재 검토가 필요한 성공 사례가 아닙니다.")
        detail = MarkerPatternSignatureService.case_detail(build, event_id, "CORE")
        if detail is None:
            raise HTTPException(404, "패턴 상세를 계산할 수 없습니다.")
        return {**row, **detail, "outlier_threshold": threshold, "top_feature_differences": detail["top_feature_differences"][:3]}

    def decide(self, marker_id: int, event_id: int, decision: str, reason: str | None) -> dict[str, Any]:
        event = self.db.execute(text("""
            SELECT id, marker_id, review_result FROM chart_marker_events
            WHERE id=:event_id AND marker_id=:marker_id
        """), {"event_id": event_id, "marker_id": marker_id}).mappings().first()
        if event is None:
            raise HTTPException(404, "차트마커 사례를 찾을 수 없습니다.")
        if event["review_result"] not in {"S", "SUCCESS"}:
            raise HTTPException(409, "성공(S) 사례만 학습 포함 여부를 결정할 수 있습니다.")
        now = datetime.now().isoformat(timespec="seconds")
        self.db.execute(text("""
            INSERT INTO chart_marker_learning_decisions
                (chart_marker_event_id, decision, decision_reason, pattern_algorithm_version, created_at, updated_at)
            VALUES (:event_id, :decision, :reason, :version, :now, :now)
            ON CONFLICT(chart_marker_event_id) DO UPDATE SET
                decision=excluded.decision,
                decision_reason=excluded.decision_reason,
                pattern_algorithm_version=excluded.pattern_algorithm_version,
                updated_at=excluded.updated_at
        """), {"event_id": event_id, "decision": decision, "reason": reason, "version": PATTERN_SIMILARITY_ALGORITHM_VERSION, "now": now})
        self.db.commit()
        return {
            "chart_marker_event_id": event_id,
            "decision": decision,
            "decision_reason": reason,
            "pattern_algorithm_version": PATTERN_SIMILARITY_ALGORITHM_VERSION,
            "updated_at": now,
        }
