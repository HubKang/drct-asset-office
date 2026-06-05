from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from backend.app.repositories.analysis_indicator_repository import AnalysisIndicatorRepository


SUPPORTED_CALCULATION_TYPES = {
    "moving_average",
    "distance_pct",
    "ratio_to_previous",
    "ratio_to_average",
    "rolling_high",
    "rolling_low",
    "distance_to_rolling_high_pct",
    "distance_to_rolling_low_pct",
    "slope",
    "between_lines",
    "band_value",
    "band_touch",
    "cross_up",
    "cross_down",
    "candle_body_pct",
    "candle_range_pct",
}
SUPPORTED_EXECUTION_CALCULATION_TYPES = {"distance_pct"}
VALID_USAGE = {"entry_filter", "success_criteria", "failure_criteria", "reference"}


class PatternGoalGptResultService:
    def __init__(self, db: Session) -> None:
        self.repo = AnalysisIndicatorRepository(db)

    def validate(self, goal_text: str, gpt_result_text: str, parsed_goal: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            payload, error_message = self._decode_payload(gpt_result_text)
            if error_message:
                return self._invalid_json(error_message)
            if not isinstance(payload, dict):
                return self._invalid_json("최상위 JSON은 객체여야 합니다.")

            has_conditions = isinstance(payload.get("conditions"), dict)
            has_new_candidates = isinstance(payload.get("new_indicator_candidates"), list)
            if not has_conditions and not has_new_candidates:
                return self._validation_failed("필수 필드 누락: conditions 또는 new_indicator_candidates 항목이 필요합니다.", payload)

            indicators = self.repo.list_indicators(active_only=True)
            indicator_map = {str(row.get("indicator_key")): row for row in indicators}
            new_candidates_raw = payload.get("new_indicator_candidates") or []
            if not isinstance(new_candidates_raw, list):
                return self._validation_failed("신규 지표 후보 검증 실패: new_indicator_candidates는 배열이어야 합니다.", payload)
            new_candidate_keys = {
                str(item.get("indicator_key") or "").strip()
                for item in new_candidates_raw
                if isinstance(item, dict)
            }

            validated_conditions: list[dict[str, Any]] = []
            conditions = payload.get("conditions") or {}
            if isinstance(conditions, dict):
                for category in ("success_criteria", "failure_criteria", "entry_filters", "exclude_filters", "reference_conditions"):
                    condition_rows = conditions.get(category) or []
                    if not isinstance(condition_rows, list):
                        return self._validation_failed(f"필수 필드 형식 오류: conditions.{category}는 배열이어야 합니다.", payload)
                    for raw_condition in condition_rows:
                        if isinstance(raw_condition, dict):
                            validated_conditions.append(
                                self._validate_condition(raw_condition, category, indicator_map, new_candidate_keys)
                            )

            new_indicator_candidates = [
                self._validate_new_indicator_candidate(item, indicator_map)
                for item in new_candidates_raw
                if isinstance(item, dict)
            ]

            return {
                "status": "success",
                "validated_conditions": validated_conditions,
                "new_indicator_candidates": new_indicator_candidates,
                "unsupported_items": self._normalize_message_items(payload.get("unsupported_items")),
                "warnings": self._normalize_message_items(payload.get("warnings")),
                "interpretation_conflicts": self._normalize_interpretation_conflicts(payload.get("interpretation_conflicts")),
                "raw_error": "",
                "validation_message": "",
                "parsed_json": payload,
            }
        except Exception as exc:
            return self._validation_failed(f"GPT 결과 검증 중 서버 내부 오류가 발생했습니다: {exc}")

    def _validate_condition(
        self,
        raw: dict[str, Any],
        group: str,
        indicator_map: dict[str, dict[str, Any]],
        new_candidate_keys: set[str],
    ) -> dict[str, Any]:
        category = str(raw.get("category") or group).replace("entry_filters", "entry_filter").replace("exclude_filters", "exclude_filter")
        if group == "reference_conditions":
            category = "reference"
        indicator_key = str(raw.get("indicator_key") or "").strip()
        condition = {
            "source_text": raw.get("source_text") or "",
            "label": raw.get("label") or raw.get("source_text") or indicator_key,
            "indicator_key": indicator_key,
            "operator": raw.get("operator") or "=",
            "value": raw.get("value"),
            "category": category,
            "expression": raw.get("expression") or self._expression_for(indicator_key, raw.get("operator") or "=", raw.get("value")),
            "apply_to_samples": False,
            "needs_review": bool(raw.get("needs_review", True)),
            "reason": raw.get("reason"),
            "source": "gpt_candidate",
        }
        messages: list[str] = []
        validation_status = "valid"
        indicator = indicator_map.get(indicator_key)
        if not indicator:
            if indicator_key in new_candidate_keys:
                validation_status = "new_indicator_required"
                messages.append("신규 지표 후보 등록 또는 1회성 사용 검토가 필요합니다.")
            else:
                validation_status = "rejected"
                messages.append("catalog에 없는 indicator_key이며 신규 지표 후보에도 없습니다.")
        else:
            if category == "entry_filter" and int(indicator.get("is_entry_allowed") or 0) != 1:
                validation_status = "rejected"
                messages.append("진입조건으로 허용되지 않은 지표입니다.")
            if category == "success_criteria" and int(indicator.get("is_success_allowed") or 0) != 1:
                validation_status = "rejected"
                messages.append("성공 기준으로 허용되지 않은 지표입니다.")
            if category == "failure_criteria" and int(indicator.get("is_failure_allowed") or 0) != 1:
                validation_status = "rejected"
                messages.append("실패 기준으로 허용되지 않은 지표입니다.")
            if str(indicator.get("category") or "") == "future_result" and category == "entry_filter":
                validation_status = "rejected"
                messages.append("미래 결과 지표는 진입조건에 사용할 수 없습니다.")
            allowed_ops = self._json_loads(indicator.get("allowed_operators_json"), [])
            if allowed_ops and condition["operator"] not in allowed_ops:
                validation_status = "needs_review" if validation_status != "rejected" else validation_status
                messages.append("허용 연산자 목록에 없는 operator입니다.")
        if not self._valid_value(condition["operator"], condition["value"]):
            validation_status = "needs_review" if validation_status != "rejected" else validation_status
            messages.append("value 형식을 확인해야 합니다.")
        if condition["needs_review"] and validation_status == "valid":
            validation_status = "needs_review"
            messages.append("GPT가 사용자 확인 필요로 표시했습니다.")
        condition["validation_status"] = validation_status
        condition["validation_message"] = " ".join(messages)
        return condition

    def _validate_new_indicator_candidate(self, raw: dict[str, Any], indicator_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
        key = str(raw.get("indicator_key") or "").strip()
        required = [str(item).strip() for item in raw.get("required_indicators") or [] if str(item).strip()]
        usage = [str(item).strip() for item in raw.get("usage") or [] if str(item).strip()]
        messages: list[str] = []
        validation_status = "calculatable"
        if not key:
            validation_status = "rejected"
            messages.append("indicator_key가 비어 있습니다.")
        if key in indicator_map:
            validation_status = "existing_duplicate"
            messages.append("이미 같은 indicator_key가 존재합니다.")
        missing = [item for item in required if item not in indicator_map]
        if missing:
            validation_status = "missing_required_indicator"
            messages.append(f"필수 지표가 없습니다: {', '.join(missing)}")
        calculation_type = str(raw.get("calculation_type") or "")
        parameters = raw.get("parameters") or {}
        if not isinstance(parameters, dict):
            parameters = {}
        if calculation_type == "distance_pct":
            if not parameters.get("target_indicator") and required:
                parameters["target_indicator"] = required[0]
            if not parameters.get("base_indicator") and len(required) >= 2:
                parameters["base_indicator"] = required[1]
            parameters.setdefault("unit", "%")
        if calculation_type not in SUPPORTED_CALCULATION_TYPES:
            validation_status = "needs_engine"
            messages.append("현재 DrCT 계산 엔진 지원 목록에 없는 calculation_type입니다.")
        if raw.get("parameters") is not None and not isinstance(raw.get("parameters"), dict):
            validation_status = "invalid_parameters"
            messages.append("parameters는 객체여야 합니다.")
        execution_supported = validation_status == "calculatable" and calculation_type in SUPPORTED_EXECUTION_CALCULATION_TYPES
        execution_status = "supported" if execution_supported else ("needs_engine" if calculation_type not in SUPPORTED_EXECUTION_CALCULATION_TYPES else validation_status)
        execution_message = (
            "distance_pct 계산 유형은 샘플 엔진에서 실행 가능합니다."
            if execution_supported
            else f"{calculation_type or '-'} 계산 유형은 아직 샘플 실행 엔진에서 지원하지 않습니다."
        )
        if bool(raw.get("lookahead_risk")):
            validation_status = "lookahead_risk"
            messages.append("미래정보 사용 위험이 있어 바로 사용할 수 없습니다.")
        invalid_usage = [item for item in usage if item not in VALID_USAGE]
        if invalid_usage:
            validation_status = "rejected"
            messages.append(f"허용되지 않은 usage입니다: {', '.join(invalid_usage)}")
        if usage and set(usage) == {"reference"} and validation_status == "calculatable":
            validation_status = "reference_only"
            messages.append("참고용 지표 후보입니다.")
        return {
            "source_text": raw.get("source_text"),
            "indicator_key": key,
            "indicator_name": raw.get("indicator_name") or key,
            "description": raw.get("description"),
            "calculation_type": calculation_type,
            "formula_description": raw.get("formula_description"),
            "required_indicators": required,
            "parameters": parameters,
            "usage": usage,
            "lookahead_risk": bool(raw.get("lookahead_risk")),
            "validation_status": validation_status,
            "validation_message": " ".join(messages) or "검증되었습니다.",
            "execution_supported": execution_supported,
            "execution_status": execution_status,
            "execution_message": execution_message,
            "decision_status": "pending",
        }

    @staticmethod
    def _decode_payload(text: str) -> tuple[dict[str, Any] | None, str]:
        cleaned = (text or "").replace("```json", "").replace("```", "").strip()
        if not cleaned:
            return None, "GPT 결과 JSON이 비어 있습니다."
        decoder = json.JSONDecoder()
        try:
            payload = json.loads(cleaned)
            return (payload, "") if isinstance(payload, dict) else (None, "최상위 JSON은 객체여야 합니다.")
        except json.JSONDecodeError as full_error:
            decoded_objects: list[dict[str, Any]] = []
            for match in re.finditer(r"\{", cleaned):
                try:
                    candidate, _ = decoder.raw_decode(cleaned[match.start():])
                except json.JSONDecodeError:
                    continue
                if isinstance(candidate, dict):
                    decoded_objects.append(candidate)
            if decoded_objects:
                return decoded_objects[-1], ""
            if "DrCT" in cleaned or "요청문" in cleaned or "schema" in cleaned:
                return None, "JSON 형식 오류: DrCT 요청문 전체가 붙여넣어진 것으로 보입니다. ChatGPT 응답의 JSON 객체만 붙여넣어 주세요."
            return None, f"JSON 형식 오류: {full_error}"

    @staticmethod
    def _normalize_message_items(items: Any) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        source_items = items if isinstance(items, list) else ([] if not items else [items])
        for item in source_items:
            if isinstance(item, str):
                normalized.append({"source_text": "", "message": item})
            elif isinstance(item, dict):
                message = item.get("message") or item.get("reason") or item.get("text") or item.get("validation_message") or ""
                normalized.append({"source_text": str(item.get("source_text") or item.get("natural_text") or ""), "message": str(message)})
            else:
                normalized.append({"source_text": "", "message": str(item)})
        return [item for item in normalized if item["message"]]

    @staticmethod
    def _normalize_interpretation_conflicts(items: Any) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        source_items = items if isinstance(items, list) else ([] if not items else [items])
        for item in source_items:
            if isinstance(item, dict):
                normalized.append(
                    {
                        "source_text": str(item.get("source_text") or ""),
                        "drct_first_pass": str(item.get("drct_first_pass") or ""),
                        "gpt_correction": str(item.get("gpt_correction") or item.get("message") or ""),
                        "suggested_indicator_key": str(item.get("suggested_indicator_key") or item.get("indicator_key") or ""),
                    }
                )
            elif isinstance(item, str):
                normalized.append({"source_text": "", "drct_first_pass": "", "gpt_correction": item, "suggested_indicator_key": ""})
        return [item for item in normalized if item["source_text"] or item["drct_first_pass"] or item["gpt_correction"] or item["suggested_indicator_key"]]

    @staticmethod
    def _json_loads(raw: Any, fallback: Any) -> Any:
        try:
            return json.loads(str(raw or ""))
        except (TypeError, json.JSONDecodeError):
            return fallback

    @staticmethod
    def _expression_for(indicator_key: str, operator: str, value: Any) -> str:
        if operator == "between" and isinstance(value, list) and len(value) == 2:
            return f"{value[0]} <= {indicator_key} <= {value[1]}"
        rendered = str(value).lower() if isinstance(value, bool) else value
        return f"{indicator_key} {operator} {rendered}".strip()

    @staticmethod
    def _valid_value(operator: str, value: Any) -> bool:
        if operator == "between":
            return isinstance(value, list) and len(value) == 2 and all(isinstance(item, int | float) for item in value)
        return isinstance(value, int | float | bool | str) or value is None

    @staticmethod
    def _invalid_json(message: str) -> dict[str, Any]:
        return {
            "status": "invalid_json",
            "validated_conditions": [],
            "new_indicator_candidates": [],
            "unsupported_items": [],
            "warnings": [],
            "interpretation_conflicts": [],
            "raw_error": message,
            "validation_message": message,
            "parsed_json": {},
        }

    @staticmethod
    def _validation_failed(message: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "status": "validation_failed",
            "validated_conditions": [],
            "new_indicator_candidates": [],
            "unsupported_items": [],
            "warnings": [],
            "interpretation_conflicts": [],
            "raw_error": message,
            "validation_message": message,
            "parsed_json": payload or {},
        }
