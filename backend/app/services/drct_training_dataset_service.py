from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.services.drct_pattern_baseline_service import PatternBaselineService
from backend.app.services.drct_pattern_feature_service import FEATURE_SCHEMA_VERSION
from backend.app.services.drct_training_case_service import TrainingCaseService, TrainingDatasetBuild
from backend.app.services.drct_rule_engine import BooleanExpression


class DrctTrainingDatasetService:
    def __init__(self, db: Session):
        self.db = db

    def _build(self, search_id: int, search_version_id: int | None) -> TrainingDatasetBuild:
        return TrainingCaseService(self.db).build(search_id, search_version_id)

    @staticmethod
    def _header(build: TrainingDatasetBuild) -> dict[str, Any]:
        return {
            "search_id": build.search_id, "search_version_id": build.search_version_id,
            "version_no": build.version_no, "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "rule_status": build.rule_status, "elapsed_ms": build.elapsed_ms, "summary": build.summary,
        }

    def readiness(self, search_id: int, search_version_id: int | None) -> dict[str, Any]:
        return self._header(self._build(search_id, search_version_id))

    def preview(self, search_id: int, search_version_id: int | None) -> dict[str, Any]:
        return self._header(self._build(search_id, search_version_id))

    @staticmethod
    def _item(case: dict[str, Any]) -> dict[str, Any]:
        return {
            "stock_id": case["stock_id"], "stock_code": case["stock_code"], "stock_name": case["stock_name"],
            "d0": case["d0"], "label": case["label"], "matched_marker_names": case["matched_marker_names"],
            "rule_status": case["rule_status"], "core_status": case["core_status"], "enriched_status": case["enriched_status"],
            "d20_return": case["outcomes"].get("d20_return"), "mfe_20": case["outcomes"].get("mfe_20"), "mae_20": case["outcomes"].get("mae_20"),
            "failed_conditions": [{key: item.get(key) for key in ("code", "label", "status", "criteria", "actual_value")}
                                  for item in case.get("rule_diagnostics", []) if item.get("status") in {"FAIL", "DATA_INCOMPLETE"}],
        }

    def cases(self, search_id: int, search_version_id: int | None, page: int, page_size: int, include_all: bool,
              rule_status: str | None = None, condition_code: str | None = None, label: str | None = None) -> dict[str, Any]:
        build = self._build(search_id, search_version_id)
        if rule_status:
            selected = [case for case in build.cases if case["rule_status"] == rule_status]
        else:
            selected = build.cases if include_all else [case for case in build.cases if case["label"] in {"SUCCESS", "FAILURE"} and case["rule_status"] == "RULE_MATCH"]
        if condition_code:
            code = condition_code.upper()
            selected = [case for case in selected if any(item.get("code") == code and item.get("status") == "FAIL" for item in case.get("rule_diagnostics", []))]
        if label:
            selected = [case for case in selected if case["label"] == label]
        start = (page - 1) * page_size
        return {"search_id": search_id, "search_version_id": build.search_version_id, "page": page, "page_size": page_size, "total": len(selected), "items": [self._item(case) for case in selected[start:start + page_size]], "elapsed_ms": build.elapsed_ms}

    def mismatch_summary(self, search_id: int, search_version_id: int | None) -> dict[str, Any]:
        build = self._build(search_id, search_version_id)
        cases = [case for case in build.cases if case["rule_status"] == "RULE_NO_MATCH"]
        by_code: dict[str, dict[str, Any]] = {}
        for case in cases:
            for diagnostic in case.get("rule_diagnostics", []):
                code = str(diagnostic.get("code", ""))
                if not code:
                    continue
                row = by_code.setdefault(code, {"code": code, "label": str(diagnostic.get("label") or code), "evaluated_count": 0, "pass_count": 0, "fail_count": 0, "incomplete_count": 0})
                row["evaluated_count"] += 1
                if diagnostic.get("status") == "PASS": row["pass_count"] += 1
                elif diagnostic.get("status") == "FAIL": row["fail_count"] += 1
                else: row["incomplete_count"] += 1
        conditions = []
        for row in by_code.values():
            row["fail_rate"] = round(row["fail_count"] / row["evaluated_count"] * 100, 1) if row["evaluated_count"] else None
            conditions.append(row)
        conditions.sort(key=lambda item: (-item["fail_rate"] if item["fail_rate"] is not None else 1, item["code"]))

        _version, rule, _status = TrainingCaseService(self.db)._version_rule(search_id, search_version_id)
        expression = str((rule or {}).get("expression", ""))
        branch_expressions = list(dict.fromkeys(re.findall(r"\(([A-Z][A-Z0-9_]*\s+AND\s+[A-Z][A-Z0-9_]*)\)", expression, re.IGNORECASE)))
        branches = []
        for branch in branch_expressions:
            counts = {"PASS": 0, "FAIL": 0, "DATA_INCOMPLETE": 0}
            evaluated = 0
            for case in cases:
                values = {str(item.get("code")): str(item.get("status")) for item in case.get("rule_diagnostics", [])}
                try:
                    result = BooleanExpression.evaluate_status(branch, values)
                except ValueError:
                    continue
                counts[result] += 1; evaluated += 1
            branches.append({"expression": branch, "label": branch.replace("AND", "그리고"), "evaluated_count": evaluated,
                             "pass_count": counts["PASS"], "fail_count": counts["FAIL"], "incomplete_count": counts["DATA_INCOMPLETE"]})
        return {"search_id": search_id, "search_version_id": build.search_version_id, "version_no": build.version_no,
                "case_count": len(cases), "conditions": conditions, "branches": branches, "elapsed_ms": build.elapsed_ms}

    def case_detail(self, search_id: int, stock_id: int, d0: str, search_version_id: int | None) -> dict[str, Any]:
        build = self._build(search_id, search_version_id)
        case = next((item for item in build.cases if item["stock_id"] == stock_id and item["d0"] == d0), None)
        if case is None:
            raise HTTPException(404, "학습 사례를 찾을 수 없습니다.")
        return {
            **self._item(case), "source_marker_event_ids": case["source_marker_event_ids"],
            "rule_diagnostics": case["rule_diagnostics"], "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "core_features": case["core_features"], "enriched_features": case["enriched_features"],
            "core_missing": case["core_missing"], "enriched_missing": case["enriched_missing"],
            "outcomes": case["outcomes"], "outcome_notice": "Future Outcome은 학습 입력에 사용하지 않습니다.",
        }

    def baseline(self, search_id: int, search_version_id: int | None, feature_profile: str) -> dict[str, Any]:
        build = self._build(search_id, search_version_id)
        result = PatternBaselineService.evaluate(build.cases, feature_profile)
        return {"search_id": search_id, "search_version_id": build.search_version_id, "version_no": build.version_no, "elapsed_ms": build.elapsed_ms, **result}
