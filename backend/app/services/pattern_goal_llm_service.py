from __future__ import annotations

import json
import re
from typing import Any

from backend.app.core.config import LMSTUDIO_MODEL
from backend.app.llm.lmstudio_client import LMStudioClient
from backend.app.services.analysis_indicator_service import AnalysisIndicatorService


ALLOWED_CATEGORIES = {"success_criteria", "failure_criteria", "entry_filter", "exclude_filter", "reference", "unsupported"}
GENERIC_FAILURE_WARNING = "LLM 보조 해석에 실패했습니다. Rule base 1차 해석 결과만 표시합니다."
SENTENCE_FAILURE_WARNING = "일부 문장 LLM 보조 해석에 실패했습니다. 성공한 후보와 Rule base 1차 해석 결과만 표시합니다."
NO_LLM_TARGET_WARNING = "LLM 보조 해석이 필요한 문장이 없어 Rule base 1차 해석 결과만 표시합니다."

CORE_INDICATOR_KEYS = [
    "close_price",
    "high_price",
    "low_price",
    "volume",
    "trading_value",
    "ma5",
    "ma10",
    "ma20",
    "ma60",
    "close_vs_ma20_pct",
    "close_vs_ma60_pct",
    "volume_vs_prev_day",
    "volume_ratio_20",
    "trading_value_vs_prev_day",
    "trading_value_ratio_20",
    "recent_3d_return",
    "recent_5d_return",
    "max_future_return_5d",
    "min_future_return_5d",
    "max_future_return_nd",
    "min_future_return_nd",
]

KEYWORD_INDICATOR_MAP = {
    ("20일선", "20일", "ma20"): {"ma20", "close_vs_ma20_pct"},
    ("10일선", "10일", "ma10"): {"ma10", "close_between_ma10_ma20"},
    ("60일선", "60일", "ma60", "상승추세"): {
        "ma60",
        "ma60_slope_5d",
        "ma60_slope_20d",
        "is_ma60_rising_5d",
        "is_ma60_rising_20d",
    },
    ("거래량",): {"volume", "prev_volume", "volume_vs_prev_day", "volume_ratio_20", "volume_ma20"},
    ("거래대금", "수급"): {
        "trading_value",
        "prev_trading_value",
        "trading_value_vs_prev_day",
        "trading_value_ratio_20",
        "trading_value_ma20",
    },
    ("눌림", "조정", "쉬어가"): {"close_vs_ma20_pct", "close_vs_ma60_pct", "recent_3d_return", "recent_5d_return"},
    ("급등", "추격매수", "과열"): {"recent_3d_return", "recent_5d_return", "close_vs_ma20_pct"},
    ("상승", "목표", "수익률"): {"max_future_return_5d", "max_future_return_nd"},
    ("손절", "하락", "손실"): {"min_future_return_5d", "min_future_return_nd"},
    ("전고점", "고점"): {"close_above_previous_high", "high_price"},
    ("양봉", "음봉", "캔들"): {"is_bullish", "is_bearish", "close_above_previous_high"},
    ("이평선 사이", "10일선과 20일선 사이"): {"ma10", "ma20", "close_between_ma10_ma20"},
}


def split_goal_text_into_sentences(goal_text: str) -> list[str]:
    protected = re.sub(r"(?<=\d)\.(?=\d)", "<DOT>", goal_text or "")
    parts = re.split(r"(?:[.!?。！？]+|\n+|;)+", protected)
    sentences: list[str] = []
    for part in parts:
        sentence = part.replace("<DOT>", ".").strip()
        sentence = re.sub(r"\s+", " ", sentence)
        if sentence and len(sentence) >= 2:
            sentences.append(sentence)
    return list(dict.fromkeys(sentences))


def build_relevant_llm_catalog(
    goal_text: str,
    first_pass_result: dict[str, Any],
    full_catalog: dict[str, Any],
    max_detail_indicators: int = 20,
    max_detail_aliases: int = 25,
    max_detail_templates: int = 10,
    mode: str = "compact",
) -> dict[str, Any]:
    if mode == "ultra_compact":
        max_detail_indicators = min(max_detail_indicators, 10)
        max_detail_aliases = min(max_detail_aliases, 8)
        max_detail_templates = min(max_detail_templates, 3)
    if mode == "sentence":
        max_detail_indicators = min(max_detail_indicators, 8)
        max_detail_aliases = min(max_detail_aliases, 8)
        max_detail_templates = min(max_detail_templates, 3)

    indicators = full_catalog.get("indicators") or []
    aliases = full_catalog.get("aliases") or []
    templates = full_catalog.get("condition_templates") or []
    indicator_map = {_indicator_key(row): row for row in indicators if _indicator_key(row)}
    selected_keys: list[str] = []
    selected_key_set: set[str] = set()

    def add_key(key: str | None) -> None:
        if not key:
            return
        for chunk in str(key).split(","):
            normalized = chunk.strip()
            if normalized and normalized in indicator_map and normalized not in selected_key_set:
                selected_key_set.add(normalized)
                selected_keys.append(normalized)

    lowered_goal = (goal_text or "").lower()
    for keywords, keys in KEYWORD_INDICATOR_MAP.items():
        if any(keyword.lower() in lowered_goal for keyword in keywords):
            for key in keys:
                add_key(key)
    for key in _extract_indicator_keys(first_pass_result):
        add_key(key)
    if not selected_keys:
        for key in CORE_INDICATOR_KEYS:
            add_key(key)
            if len(selected_keys) >= max_detail_indicators:
                break

    detailed_keys = selected_keys[:max_detail_indicators]
    detailed_key_set = set(detailed_keys)
    summary_keys = [key for key in selected_keys if key not in detailed_key_set]
    if mode == "sentence":
        summary_keys = summary_keys[:10]
    elif mode == "ultra_compact":
        summary_keys = summary_keys[:20]

    relevant_aliases = []
    for alias in aliases:
        alias_key = str(alias.get("indicator_key") or "").strip()
        alias_text = str(alias.get("alias_text") or "")
        if alias_key in selected_key_set or (alias_text and alias_text.lower() in lowered_goal):
            relevant_aliases.append(_compact_alias(alias))
        if len(relevant_aliases) >= max_detail_aliases:
            break

    relevant_templates = []
    for template in templates:
        template_text = json.dumps(template, ensure_ascii=False)
        if any(key in template_text for key in selected_key_set):
            relevant_templates.append(_compact_template(template))
        if len(relevant_templates) >= max_detail_templates:
            break

    return {
        "detailed_indicators": [_compact_indicator(indicator_map[key], detailed=True) for key in detailed_keys],
        "relevant_aliases": relevant_aliases,
        "relevant_templates": relevant_templates,
        "summary_indicators": [_compact_indicator(indicator_map[key], detailed=False) for key in summary_keys],
        "catalog_size": {
            "full_indicators": len(indicators),
            "sent_detailed_indicators": len(detailed_keys),
            "sent_summary_indicators": len(summary_keys),
            "full_aliases": len(aliases),
            "sent_aliases": len(relevant_aliases),
            "full_templates": len(templates),
            "sent_templates": len(relevant_templates),
        },
        "mode": mode,
    }


def _indicator_key(row: dict[str, Any]) -> str:
    return str(row.get("indicator_key") or row.get("key") or "").strip()


def _extract_indicator_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for field in ("indicator_key", "indicator"):
            raw = value.get(field)
            if isinstance(raw, str):
                keys.update(chunk.strip() for chunk in raw.split(",") if chunk.strip())
            elif isinstance(raw, list):
                keys.update(str(item).strip() for item in raw if str(item).strip())
        for child in value.values():
            keys.update(_extract_indicator_keys(child))
    elif isinstance(value, list):
        for item in value:
            keys.update(_extract_indicator_keys(item))
    return keys


def _compact_indicator(row: dict[str, Any], detailed: bool) -> dict[str, Any]:
    key = _indicator_key(row)
    compact = {
        "key": key,
        "name": row.get("indicator_name") or row.get("name") or key,
        "usage": row.get("allowed_usage") or row.get("usage") or [],
        "category": row.get("category"),
    }
    if detailed:
        compact.update(
            {
                "unit": row.get("unit"),
                "operators": row.get("allowed_operators") or row.get("operators") or [],
                "availability": row.get("availability"),
            }
        )
    return compact


def _compact_alias(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "text": row.get("alias_text") or row.get("text"),
        "indicator_key": row.get("indicator_key"),
        "default": {
            "category": row.get("default_category"),
            "operator": row.get("default_operator"),
            "value": row.get("default_value"),
        },
        "needs_review": row.get("needs_review"),
    }


def _compact_template(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": row.get("template_key") or row.get("key"),
        "name": row.get("template_name") or row.get("name"),
        "type": row.get("template_type") or row.get("type"),
        "summary": row.get("description") or row.get("template_name") or row.get("template_key"),
    }


class PatternGoalLLMService:
    def __init__(self, analysis_indicator_service: AnalysisIndicatorService | None = None) -> None:
        self.client = LMStudioClient()
        self.analysis_indicator_service = analysis_indicator_service

    def assist(self, goal_text: str, first_pass: dict[str, Any], catalog: dict[str, Any] | None = None) -> dict[str, Any]:
        full_catalog = catalog or (self.analysis_indicator_service.llm_catalog() if self.analysis_indicator_service else {})
        sentences = split_goal_text_into_sentences(goal_text)
        sentence_plans = self._build_sentence_plans(sentences, first_pass)
        targets = sorted(
            [plan for plan in sentence_plans if plan.get("llm_required")],
            key=self._sentence_priority,
        )[:5]
        if not targets:
            result = self.skipped()
            result["enabled"] = True
            result["warnings"] = [NO_LLM_TARGET_WARNING]
            result["sentence_results"] = sentence_plans
            result["diagnostics"] = self._sentence_diagnostics(sentence_plans, [], retry_count=0)
            return result

        sentence_results: list[dict[str, Any]] = []
        candidate_conditions: list[dict[str, Any]] = []
        suggested_additional_conditions: list[dict[str, Any]] = []
        unsupported_items: list[dict[str, Any]] = []
        missing_catalog_requests: list[dict[str, Any]] = []
        total_retry_count = 0

        for plan in targets:
            sentence = str(plan.get("sentence") or "")
            selected_catalog = build_relevant_llm_catalog(
                sentence,
                {"parsed_goal": {"entry_filters": plan.get("first_pass_matches") or []}},
                full_catalog,
                max_detail_indicators=8,
                max_detail_aliases=8,
                max_detail_templates=3,
                mode="sentence",
            )
            call_result = self._assist_sentence(sentence, selected_catalog)
            total_retry_count += int(call_result.get("retry_count") or 0)
            sentence_results.append({**plan, **call_result})
            if call_result.get("status") != "success":
                unsupported_items.append(
                    {
                        "source_text": sentence,
                        "reason": call_result.get("error_message") or "문장 단위 LLM 해석 실패",
                        "source": "llm_candidate",
                    }
                )
                continue
            merged = self._merge_sentence_payload(sentence, call_result.get("payload") or {}, selected_catalog, first_pass)
            candidate_conditions.extend(merged["candidate_conditions"])
            suggested_additional_conditions.extend(merged["suggested_additional_conditions"])
            unsupported_items.extend(merged["unsupported_items"])
            missing_catalog_requests.extend(merged["missing_catalog_requests"])

        untouched = [plan for plan in sentence_plans if not plan.get("llm_required")]
        final_sentence_results = untouched + sentence_results
        success_count = len([item for item in sentence_results if item.get("status") == "success"])
        failed_count = len([item for item in sentence_results if item.get("status") != "success"])
        if success_count and failed_count:
            status = "partial_success"
            warnings = [SENTENCE_FAILURE_WARNING]
        elif success_count:
            status = "success"
            warnings = []
        else:
            status = "failed"
            warnings = [GENERIC_FAILURE_WARNING]

        diagnostics = self._sentence_diagnostics(final_sentence_results, sentence_results, retry_count=total_retry_count)
        return {
            "enabled": True,
            "status": status,
            "model": LMSTUDIO_MODEL or self.client.model,
            "prompt_text": "",
            "raw_response": "",
            "candidate_conditions": candidate_conditions,
            "suggested_additional_conditions": suggested_additional_conditions,
            "unsupported_items": unsupported_items,
            "missing_catalog_requests": missing_catalog_requests,
            "sentence_results": final_sentence_results,
            "warnings": warnings,
            "error_message": "" if status != "failed" else "모든 대상 문장 LLM 해석에 실패했습니다.",
            "diagnostics": diagnostics,
            "debug": diagnostics,
        }

    def _build_sentence_plans(self, sentences: list[str], first_pass: dict[str, Any]) -> list[dict[str, Any]]:
        parsed_goal = first_pass.get("parsed_goal") or {}
        conditions = [
            parsed_goal.get("success_criteria") or {},
            parsed_goal.get("failure_criteria") or {},
            *(parsed_goal.get("entry_filters") or []),
            *(parsed_goal.get("exclude_filters") or []),
        ]
        unsupported = first_pass.get("unsupported_items") or []
        plans: list[dict[str, Any]] = []
        for sentence in sentences:
            matches = [item for item in conditions if self._sentence_matches_condition(sentence, item)]
            unsupported_matches = [item for item in unsupported if self._contains_similar(sentence, str(item.get("source_text") or ""))]
            if unsupported_matches:
                status = "unsupported"
                llm_required = True
                reason = "1차 해석에서 unsupported로 분류됨"
            elif not matches:
                status = "ambiguous" if self._looks_ambiguous(sentence) else "not_matched"
                llm_required = True
                reason = "1차 해석 조건에 직접 매칭되지 않음"
            elif any(str(item.get("status") or "") == "needs_review" for item in matches):
                status = "needs_review"
                llm_required = True
                reason = "1차 해석 결과가 확인 필요 상태"
            else:
                status = "parsed_by_rule"
                llm_required = False
                reason = "Rule base/DB alias/template로 명확히 해석됨"
            plans.append(
                {
                    "sentence": sentence,
                    "status": status,
                    "first_pass_matches": matches,
                    "llm_required": llm_required,
                    "reason": reason,
                }
            )
        return plans

    def _assist_sentence(self, sentence: str, selected_catalog: dict[str, Any]) -> dict[str, Any]:
        attempts = [
            {"retry_count": 0, "max_tokens": 512, "catalog": selected_catalog},
            {
                "retry_count": 1,
                "max_tokens": 768,
                "catalog": self._shrink_sentence_catalog(selected_catalog),
            },
        ]
        last_error = ""
        for attempt in attempts:
            prompt = self._build_sentence_prompt(sentence, attempt["catalog"])
            try:
                raw = self.client.generate_text(
                    prompt=prompt,
                    temperature=0,
                    max_tokens=int(attempt["max_tokens"]),
                    model=LMSTUDIO_MODEL or None,
                    purpose="pattern_goal_llm_assist",
                    system_prompt=(
                        "You map ONE Korean trading sentence to indicator condition candidates. "
                        "Return JSON only. No explanation. No markdown. Use only provided indicator keys."
                    ),
                )
                payload = self._parse_json_object(raw)
                if not payload:
                    raise RuntimeError("invalid_json")
                return {
                    "status": "success",
                    "candidate_count": len(payload.get("conditions") or []),
                    "finish_reason": "stop",
                    "retry_count": attempt["retry_count"],
                    "prompt_char_length": len(prompt),
                    "catalog_size": attempt["catalog"].get("catalog_size") or {},
                    "payload": payload,
                    "error_message": "",
                }
            except Exception as exc:
                last_error = str(exc)
                if not self._should_retry_sentence_error(exc) or int(attempt["retry_count"]) >= 1:
                    break
        return {
            "status": "failed",
            "candidate_count": 0,
            "finish_reason": self._finish_reason_from_error(last_error),
            "retry_count": 1 if self._should_retry_sentence_error(RuntimeError(last_error)) else 0,
            "error_message": last_error,
        }

    def _build_sentence_prompt(self, sentence: str, selected_catalog: dict[str, Any]) -> str:
        indicators = [
            {"key": item.get("key"), "name": item.get("name"), "unit": item.get("unit"), "usage": item.get("usage")}
            for item in selected_catalog.get("detailed_indicators", [])
        ]
        if selected_catalog.get("summary_indicators"):
            indicators.extend(
                {"key": item.get("key"), "name": item.get("name")}
                for item in selected_catalog.get("summary_indicators", [])
            )
        return (
            f"sentence:{json.dumps(sentence, ensure_ascii=False)}\n"
            f"available_indicators:{json.dumps(indicators, ensure_ascii=False, separators=(',', ':'))}\n"
            'Return JSON:{"sentence":"","conditions":[],"unsupported":false,"missing_catalog_requests":[]}'
        )

    def _merge_sentence_payload(
        self,
        sentence: str,
        payload: dict[str, Any],
        selected_catalog: dict[str, Any],
        first_pass: dict[str, Any],
    ) -> dict[str, list[dict[str, Any]]]:
        indicator_map = self._selected_indicator_map(selected_catalog)
        existing_keys = self._existing_condition_keys(first_pass)
        candidate_conditions: list[dict[str, Any]] = []
        suggested_additional_conditions: list[dict[str, Any]] = []
        unsupported_items: list[dict[str, Any]] = []
        missing_catalog_requests: list[dict[str, Any]] = []

        for raw in (payload.get("conditions") or [])[:3]:
            if not isinstance(raw, dict):
                continue
            condition = self._normalize_sentence_condition(sentence, raw, indicator_map)
            condition_key = self._condition_key(condition)
            if condition_key in existing_keys:
                continue
            if condition.get("validation_status") == "rejected":
                unsupported_items.append(
                    {
                        "source_text": sentence,
                        "reason": condition.get("validation_message") or "선별 catalog에 없는 지표",
                        "source": "llm_candidate",
                    }
                )
                continue
            target = suggested_additional_conditions if condition.get("needs_review") else candidate_conditions
            target.append(condition)

        for item in payload.get("missing_catalog_requests") or []:
            if isinstance(item, dict):
                missing_catalog_requests.append(
                    {
                        **item,
                        "source_text": item.get("source_text") or sentence,
                        "source": "llm_candidate",
                        "validation_status": "catalog_missing",
                        "status": "catalog_missing",
                    }
                )
        if payload.get("unsupported"):
            unsupported_items.append(
                {
                    "source_text": sentence,
                    "reason": payload.get("reason") or "제공 catalog로 해석할 수 없음",
                    "source": "llm_candidate",
                }
            )
        return {
            "candidate_conditions": candidate_conditions,
            "suggested_additional_conditions": suggested_additional_conditions,
            "unsupported_items": unsupported_items,
            "missing_catalog_requests": missing_catalog_requests,
        }

    def _normalize_sentence_condition(
        self,
        sentence: str,
        raw: dict[str, Any],
        indicator_map: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        indicator_key = str(raw.get("indicator_key") or "").strip()
        category = str(raw.get("category") or "entry_filter")
        if category not in ALLOWED_CATEGORIES:
            category = "entry_filter"
        operator = str(raw.get("operator") or "=")
        value = raw.get("value")
        condition = {
            "source_text": sentence,
            "natural_text": sentence,
            "label": str(raw.get("label") or sentence)[:60],
            "category": category,
            "indicator_key": indicator_key,
            "indicator": indicator_key,
            "operator": operator,
            "value": value,
            "expression": raw.get("expression") or self._expression_for(indicator_key, operator, value),
            "status": "needs_review" if raw.get("needs_review", True) else "needs_review",
            "source": "llm_candidate",
            "confidence": raw.get("confidence", 0.5),
            "apply_to_samples": False,
            "needs_review": bool(raw.get("needs_review", True)),
        }
        messages: list[str] = []
        validation_status = "valid"
        indicator = indicator_map.get(indicator_key)
        if not indicator:
            validation_status = "rejected"
            messages.append("선별 catalog에 없는 indicator_key입니다.")
        else:
            usage = set(indicator.get("usage") or [])
            if category == "entry_filter" and "entry_filter" not in usage:
                validation_status = "rejected"
                messages.append("해당 지표는 진입조건으로 사용할 수 없습니다.")
            if indicator.get("category") == "future_result" and category == "entry_filter":
                validation_status = "rejected"
                messages.append("future_result 지표는 진입조건으로 사용할 수 없습니다.")
            operators = set(indicator.get("operators") or [])
            if operators and operator not in operators:
                validation_status = "needs_review" if validation_status != "rejected" else validation_status
                messages.append("허용 연산자 목록에 없는 operator입니다.")
        try:
            if float(condition.get("confidence", 0)) < 0.7 and validation_status == "valid":
                validation_status = "needs_review"
                messages.append("신뢰도가 낮아 확인이 필요합니다.")
        except (TypeError, ValueError):
            validation_status = "needs_review"
            messages.append("confidence 값이 숫자가 아닙니다.")
        condition["validation_status"] = validation_status
        condition["validation_message"] = " ".join(messages)
        return condition

    @staticmethod
    def _selected_indicator_map(selected_catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
        rows = (selected_catalog.get("detailed_indicators") or []) + (selected_catalog.get("summary_indicators") or [])
        return {str(item.get("key")): item for item in rows if item.get("key")}

    @staticmethod
    def _existing_condition_keys(first_pass: dict[str, Any]) -> set[tuple[str, str, str]]:
        parsed_goal = first_pass.get("parsed_goal") or {}
        rows = [
            *(parsed_goal.get("entry_filters") or []),
            *(parsed_goal.get("exclude_filters") or []),
        ]
        return {PatternGoalLLMService._condition_key(row) for row in rows}

    @staticmethod
    def _condition_key(condition: dict[str, Any]) -> tuple[str, str, str]:
        return (
            str(condition.get("indicator_key") or condition.get("indicator") or ""),
            str(condition.get("operator") or ""),
            json.dumps(condition.get("value", None), ensure_ascii=False, sort_keys=True),
        )

    @staticmethod
    def _expression_for(indicator_key: str, operator: str, value: Any) -> str:
        if operator == "between" and isinstance(value, list) and len(value) == 2:
            return f"{value[0]} <= {indicator_key} <= {value[1]}"
        rendered = str(value).lower() if isinstance(value, bool) else value
        return f"{indicator_key} {operator} {rendered}".strip()

    @staticmethod
    def _shrink_sentence_catalog(selected_catalog: dict[str, Any]) -> dict[str, Any]:
        next_catalog = dict(selected_catalog)
        next_catalog["detailed_indicators"] = (selected_catalog.get("detailed_indicators") or [])[:5]
        next_catalog["relevant_aliases"] = (selected_catalog.get("relevant_aliases") or [])[:3]
        next_catalog["relevant_templates"] = []
        next_catalog["summary_indicators"] = [
            {"key": item.get("key"), "name": item.get("name")}
            for item in (selected_catalog.get("summary_indicators") or [])[:5]
        ]
        size = dict(selected_catalog.get("catalog_size") or {})
        size.update(
            {
                "sent_detailed_indicators": len(next_catalog["detailed_indicators"]),
                "sent_summary_indicators": len(next_catalog["summary_indicators"]),
                "sent_aliases": len(next_catalog["relevant_aliases"]),
                "sent_templates": 0,
            }
        )
        next_catalog["catalog_size"] = size
        next_catalog["mode"] = "sentence_retry"
        return next_catalog

    @staticmethod
    def _sentence_matches_condition(sentence: str, condition: dict[str, Any]) -> bool:
        source = str(condition.get("source_text") or condition.get("natural_text") or condition.get("label") or "")
        return PatternGoalLLMService._contains_similar(sentence, source)

    @staticmethod
    def _contains_similar(left: str, right: str) -> bool:
        normalized_left = re.sub(r"\s+", "", left or "")
        normalized_right = re.sub(r"\s+", "", right or "")
        if not normalized_left or not normalized_right:
            return False
        return normalized_left in normalized_right or normalized_right in normalized_left

    @staticmethod
    def _looks_ambiguous(sentence: str) -> bool:
        return bool(re.search(r"(거래량|거래대금|수급|힘|세력|부근|근처).*(\d+(?:\.\d+)?\s*배|붙|유입|들어)", sentence))

    @staticmethod
    def _sentence_priority(plan: dict[str, Any]) -> int:
        order = {
            "unsupported": 0,
            "ambiguous": 1,
            "not_matched": 2,
            "needs_review": 3,
        }
        return order.get(str(plan.get("status") or ""), 9)

    @staticmethod
    def _should_retry_sentence_error(exc: Exception) -> bool:
        message = str(exc).lower()
        return any(token in message for token in ("empty content", "finish_reason=length", "length", "invalid_json", "context", "tokens", "exceeds"))

    @staticmethod
    def _finish_reason_from_error(message: str) -> str:
        match = re.search(r"finish_reason=([a-zA-Z_]+)", message or "")
        if match:
            return match.group(1)
        if "length" in (message or "").lower():
            return "length"
        return "error"

    @staticmethod
    def _sentence_diagnostics(
        all_sentence_results: list[dict[str, Any]],
        llm_sentence_results: list[dict[str, Any]],
        retry_count: int,
    ) -> dict[str, Any]:
        success_count = len([item for item in llm_sentence_results if item.get("status") == "success"])
        failed_count = len([item for item in llm_sentence_results if item.get("status") != "success"])
        return {
            "sentence_count": len(all_sentence_results),
            "llm_target_sentence_count": len(llm_sentence_results),
            "llm_success_sentence_count": success_count,
            "llm_failed_sentence_count": failed_count,
            "retry_count": retry_count,
            "used_mode": "sentence",
            "model": LMSTUDIO_MODEL or "google/gemma-4-e2b",
        }

    @staticmethod
    def _parse_json_object(raw: str) -> dict[str, Any]:
        cleaned = (raw or "").replace("```json", "").replace("```", "").strip()
        try:
            parsed = json.loads(cleaned)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", cleaned)
            if not match:
                return {}
            try:
                parsed = json.loads(match.group(0))
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}

    @staticmethod
    def skipped() -> dict[str, Any]:
        return {
            "enabled": False,
            "status": "skipped",
            "model": "",
            "prompt_text": "",
            "raw_response": "",
            "candidate_conditions": [],
            "suggested_additional_conditions": [],
            "unsupported_items": [],
            "missing_catalog_requests": [],
            "sentence_results": [],
            "warnings": [],
            "error_message": "",
            "diagnostics": {},
        }
