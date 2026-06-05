from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.repositories.analysis_indicator_repository import AnalysisIndicatorRepository


class AnalysisIndicatorService:
    def __init__(self, db: Session) -> None:
        self.repo = AnalysisIndicatorRepository(db)

    @staticmethod
    def _payload(model: Any) -> dict[str, Any]:
        return model.model_dump(exclude_unset=True) if hasattr(model, "model_dump") else model.dict(exclude_unset=True)

    @staticmethod
    def _json_loads(raw: Any, fallback: Any) -> Any:
        try:
            return json.loads(str(raw or ""))
        except (TypeError, json.JSONDecodeError):
            return fallback

    @staticmethod
    def _validate_json_text(value: str | None, field_name: str) -> None:
        if value in (None, ""):
            return
        try:
            json.loads(value)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field_name} JSON ?뺤떇???щ컮瑜댁? ?딆뒿?덈떎: {exc}") from exc

    def list_indicators(
        self,
        keyword: str | None,
        source_type: str | None,
        category: str | None,
        active_only: bool,
        available_for_llm: bool | None,
    ) -> dict[str, Any]:
        return {
            "items": self.repo.list_indicators(
                keyword=keyword,
                source_type=source_type,
                category=category,
                active_only=active_only,
                available_for_llm=available_for_llm,
            )
        }

    def create_indicator(self, payload: Any) -> dict[str, Any]:
        values = self._payload(payload)
        self._validate_json_text(values.get("parameters_json"), "parameters_json")
        self._validate_json_text(values.get("required_columns_json"), "required_columns_json")
        self._validate_json_text(values.get("allowed_operators_json"), "allowed_operators_json")
        self._validate_json_text(values.get("default_value_json"), "default_value_json")
        return self.repo.create_indicator(values)

    def update_indicator(self, indicator_id: int, payload: Any) -> dict[str, Any]:
        values = self._payload(payload)
        self._validate_json_text(values.get("parameters_json"), "parameters_json")
        self._validate_json_text(values.get("required_columns_json"), "required_columns_json")
        self._validate_json_text(values.get("allowed_operators_json"), "allowed_operators_json")
        self._validate_json_text(values.get("default_value_json"), "default_value_json")
        row = self.repo.update_indicator(indicator_id, values)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="吏??湲곗??뺣낫瑜?李얠쓣 ???놁뒿?덈떎.")
        return row

    def delete_indicator(self, indicator_id: int) -> dict[str, Any]:
        row = self.repo.soft_delete_indicator(indicator_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="吏??湲곗??뺣낫瑜?李얠쓣 ???놁뒿?덈떎.")
        return row

    def list_aliases(self, keyword: str | None, indicator_key: str | None, active_only: bool) -> dict[str, Any]:
        return {"items": self.repo.list_aliases(keyword=keyword, indicator_key=indicator_key, active_only=active_only)}

    def create_alias(self, payload: Any) -> dict[str, Any]:
        values = self._payload(payload)
        self._validate_json_text(values.get("default_value_json"), "default_value_json")
        return self.repo.create_alias(values)

    def update_alias(self, alias_id: int, payload: Any) -> dict[str, Any]:
        values = self._payload(payload)
        self._validate_json_text(values.get("default_value_json"), "default_value_json")
        row = self.repo.update_alias(alias_id, values)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="?먯뿰??蹂꾩묶??李얠쓣 ???놁뒿?덈떎.")
        return row

    def delete_alias(self, alias_id: int) -> dict[str, Any]:
        row = self.repo.soft_delete_alias(alias_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="?먯뿰??蹂꾩묶??李얠쓣 ???놁뒿?덈떎.")
        return row

    def list_templates(self, active_only: bool) -> dict[str, Any]:
        return {"items": self.repo.list_templates(active_only=active_only)}

    def create_template(self, payload: Any) -> dict[str, Any]:
        values = self._payload(payload)
        self._validate_json_text(values.get("condition_json"), "condition_json")
        return self.repo.create_template(values)

    def update_template(self, template_id: int, payload: Any) -> dict[str, Any]:
        values = self._payload(payload)
        self._validate_json_text(values.get("condition_json"), "condition_json")
        row = self.repo.update_template(template_id, values)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="議곌굔 ?쒗뵆由우쓣 李얠쓣 ???놁뒿?덈떎.")
        return row

    def delete_template(self, template_id: int) -> dict[str, Any]:
        row = self.repo.soft_delete_template(template_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="議곌굔 ?쒗뵆由우쓣 李얠쓣 ???놁뒿?덈떎.")
        return row

    def list_candidates(self, status: str | None, keyword: str | None, active_only: bool) -> dict[str, Any]:
        return {"items": self.repo.list_candidates(status=status, keyword=keyword, active_only=active_only)}

    def create_candidate(self, payload: Any) -> dict[str, Any]:
        values = self._payload(payload)
        self._validate_json_text(values.get("parameters_json"), "parameters_json")
        self._validate_json_text(values.get("required_indicators_json"), "required_indicators_json")
        self._validate_json_text(values.get("usage_json"), "usage_json")
        return self.repo.create_candidate(values)

    def update_candidate(self, candidate_id: int, payload: Any) -> dict[str, Any]:
        values = self._payload(payload)
        self._validate_json_text(values.get("parameters_json"), "parameters_json")
        self._validate_json_text(values.get("required_indicators_json"), "required_indicators_json")
        self._validate_json_text(values.get("usage_json"), "usage_json")
        row = self.repo.update_candidate(candidate_id, values)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GPT 제안 지표 후보를 찾을 수 없습니다.")
        return row

    def mark_candidate(self, candidate_id: int, decision_status: str) -> dict[str, Any]:
        row = self.repo.update_candidate(candidate_id, {"decision_status": decision_status})
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GPT 제안 지표 후보를 찾을 수 없습니다.")
        return row

    def approve_candidate_as_indicator(self, candidate_id: int) -> dict[str, Any]:
        candidate = self.repo.get_candidate(candidate_id)
        if not candidate:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GPT 제안 지표 후보를 찾을 수 없습니다.")
        key = str(candidate.get("suggested_indicator_key") or "").strip()
        duplicate = [row for row in self.repo.list_indicators(active_only=False) if row.get("indicator_key") == key]
        if duplicate:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="이미 같은 indicator_key가 존재합니다.")
        usage = self._json_loads(candidate.get("usage_json"), ["reference"])
        calculation_type = str(candidate.get("calculation_type") or "").strip()
        execution_supported = calculation_type == "distance_pct"
        indicator = self.repo.create_indicator(
            {
                "indicator_key": key,
                "indicator_name": candidate.get("suggested_indicator_name") or key,
                "description": candidate.get("description"),
                "source_type": "calculated",
                "calculation_formula": candidate.get("formula_description"),
                "calculation_type": calculation_type,
                "parameters_json": candidate.get("parameters_json") or "{}",
                "required_columns_json": candidate.get("required_indicators_json") or "[]",
                "data_type": "number" if execution_supported else "boolean",
                "unit": "%" if execution_supported else None,
                "category": "gpt_candidate",
                "allowed_operators_json": '[">", ">=", "<", "<=", "between", "=", "!="]' if execution_supported else '["=", "!="]',
                "default_operator": "between" if execution_supported else "=",
                "default_value_json": "[-1.5, 1.5]" if execution_supported else "true",
                "example_expressions": candidate.get("source_text"),
                "is_available_for_rule": 1,
                "is_available_for_llm": 1,
                "is_entry_allowed": 1 if "entry_filter" in usage else 0,
                "is_success_allowed": 1 if "success_criteria" in usage else 0,
                "is_failure_allowed": 1 if "failure_criteria" in usage else 0,
                "needs_review_default": 1,
                "execution_supported": 1 if execution_supported else 0,
                "execution_status": "supported" if execution_supported else "needs_engine",
                "execution_message": "distance_pct 계산 유형은 샘플 엔진에서 실행 가능합니다." if execution_supported else "아직 샘플 실행 엔진이 지원하지 않는 계산 유형입니다.",
                "is_active": 1,
                "sort_order": 9000,
            }
        )
        return self.repo.update_candidate(
            candidate_id,
            {"decision_status": "approved_as_indicator", "linked_indicator_id": indicator.get("id")},
        ) or {}
    def llm_catalog(self) -> dict[str, Any]:
        indicators = self.repo.list_indicators(active_only=True, available_for_llm=True)
        aliases = self.repo.list_aliases(active_only=True)
        templates = [row for row in self.repo.list_templates(active_only=True) if int(row.get("is_available_for_llm") or 0) == 1]
        return {
            "indicators": [self._catalog_indicator(row) for row in indicators],
            "aliases": [self._catalog_alias(row) for row in aliases],
            "condition_templates": [self._catalog_template(row) for row in templates],
        }

    def _catalog_indicator(self, row: dict[str, Any]) -> dict[str, Any]:
        allowed_usage: list[str] = []
        if int(row.get("is_entry_allowed") or 0):
            allowed_usage.append("entry_filter")
        if int(row.get("is_success_allowed") or 0):
            allowed_usage.append("success_criteria")
        if int(row.get("is_failure_allowed") or 0):
            allowed_usage.append("failure_criteria")
        if not allowed_usage:
            allowed_usage.append("reference")
        return {
            "indicator_key": row.get("indicator_key"),
            "indicator_name": row.get("indicator_name"),
            "availability": "calculatable" if row.get("source_type") == "calculated" else row.get("source_type"),
            "source_type": row.get("source_type"),
            "formula": row.get("calculation_formula"),
            "required_columns": self._json_loads(row.get("required_columns_json"), []),
            "allowed_usage": allowed_usage,
            "allowed_operators": self._json_loads(row.get("allowed_operators_json"), []),
            "unit": row.get("unit"),
            "description": row.get("description"),
            "category": row.get("category"),
            "default_operator": row.get("default_operator"),
            "default_value": self._json_loads(row.get("default_value_json"), None),
        }

    def _catalog_alias(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "alias_text": row.get("alias_text"),
            "indicator_key": row.get("indicator_key"),
            "match_type": row.get("match_type"),
            "default_category": row.get("default_category"),
            "default_operator": row.get("default_operator"),
            "default_value": self._json_loads(row.get("default_value_json"), None),
            "apply_to_samples_default": bool(row.get("apply_to_samples_default")),
            "needs_review": bool(row.get("needs_review")),
            "confidence": row.get("confidence"),
        }

    def _catalog_template(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "template_key": row.get("template_key"),
            "template_name": row.get("template_name"),
            "template_type": row.get("template_type"),
            "conditions": self._json_loads(row.get("condition_json"), {}),
            "default_apply_to_samples": bool(row.get("default_apply_to_samples")),
            "needs_review": bool(row.get("needs_review")),
            "description": row.get("description"),
        }

