from __future__ import annotations

from copy import deepcopy
import re
from typing import Any


SUPPORTED_SCENARIO_INDICATORS: dict[str, dict[str, Any]] = {
    "ma20_slope_5d": {
        "display_name": "20일선 5일 기울기",
        "supported_operators": [">", ">=", "<", "<="],
        "roles": ["trend"],
        "value_type": "number",
    },
    "ma60_slope_5d": {
        "display_name": "60일선 5일 기울기",
        "supported_operators": [">", ">=", "<", "<="],
        "roles": ["trend"],
        "value_type": "number",
    },
    "close_vs_ma20_pct": {
        "display_name": "20일선 이격률",
        "supported_operators": [">", ">=", "<", "<=", "between"],
        "roles": ["pullback", "overheat_filter"],
        "value_type": "number",
    },
    "close_vs_ma60_pct": {
        "display_name": "60일선 이격률",
        "supported_operators": [">", ">=", "<", "<=", "between"],
        "roles": ["trend", "risk_filter"],
        "value_type": "number",
    },
    "ma5_vs_ma10_pct": {
        "display_name": "5일선·10일선 이격률",
        "supported_operators": [">", ">=", "<", "<=", "between"],
        "roles": ["short_ma_convergence"],
        "value_type": "number",
    },
    "recent_3d_return": {
        "display_name": "최근 3거래일 수익률",
        "supported_operators": [">", ">=", "<", "<=", "between"],
        "roles": ["overheat_filter", "risk_filter"],
        "value_type": "number",
    },
    "recent_5d_return": {
        "display_name": "최근 5거래일 수익률",
        "supported_operators": [">", ">=", "<", "<=", "between"],
        "roles": ["overheat_filter", "risk_filter"],
        "value_type": "number",
    },
    "recent_10d_return": {
        "display_name": "최근 10거래일 수익률",
        "supported_operators": [">", ">=", "<", "<=", "between"],
        "roles": ["overheat_filter"],
        "value_type": "number",
    },
    "max_return_1d_30d": {
        "display_name": "최근 30일 내 1일 최대 상승률",
        "supported_operators": [">", ">=", "<", "<=", "between"],
        "roles": ["overheat_filter"],
        "value_type": "number",
    },
    "trading_value_ratio_20": {
        "display_name": "20일 평균 대비 거래대금 비율",
        "supported_operators": [">", ">=", "<", "<=", "between"],
        "roles": ["volume"],
        "value_type": "number",
    },
}

SUPPORTED_OPERATORS = {">", ">=", "<", "<=", "=", "between"}
SUPPORTED_RISK_ACTIONS = {"block_add_buy", "force_stop", "exclude_entry", "warning_only"}
SUPPORTED_PRICE_BASES = {"entry_price", "average_price"}

STATUS_LABELS = {
    "simulation_ready": "시뮬레이션 가능",
    "needs_review": "검토 필요",
    "unsupported": "지원 불가",
    "risky": "위험 조건 포함",
    "invalid": "구조 오류",
}


def validate_scenario_candidates(payload: dict[str, Any]) -> dict[str, Any]:
    candidates = payload.get("candidates") or payload.get("scenario_candidates") or []
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("scenario_candidates 또는 candidates 배열이 필요합니다.")

    goal = payload.get("goal") or {}
    risk_plan = payload.get("risk_plan") or {}
    validated = [
        _validate_candidate(index, candidate, goal, risk_plan)
        for index, candidate in enumerate(candidates)
    ]
    summary = {
        "total_candidates": len(validated),
        "simulation_ready": sum(1 for item in validated if item["status"] == "simulation_ready"),
        "needs_review": sum(1 for item in validated if item["status"] == "needs_review"),
        "unsupported": sum(1 for item in validated if item["status"] == "unsupported"),
        "risky": sum(1 for item in validated if item["status"] == "risky"),
        "invalid": sum(1 for item in validated if item["status"] == "invalid"),
        "structure_error": sum(1 for item in validated if item.get("structure_error_count", 0) > 0),
        "auto_converted": sum(item.get("auto_converted_count", 0) for item in validated),
    }
    return {"summary": summary, "validated_candidates": validated}


def _validate_candidate(index: int, candidate: dict[str, Any], goal: dict[str, Any], risk_plan: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(candidate)
    scenario_name = str(candidate.get("scenario_name") or candidate.get("name") or candidate.get("title") or f"시나리오 후보 {index + 1}")
    entry_conditions = candidate.get("entry_conditions")
    risk_filters = candidate.get("risk_filters") or []
    add_buy_plan = candidate.get("add_buy_plan")

    warnings: list[str] = []
    errors: list[str] = []
    condition_results: list[dict[str, Any]] = []
    risk_filter_results: list[dict[str, Any]] = []

    if not isinstance(entry_conditions, list):
        errors.append("entry_conditions 배열이 필요합니다.")
        entry_conditions = []
        normalized["entry_conditions"] = []

    if len(entry_conditions) == 0:
        errors.append("진입 조건이 없습니다.")
    elif len(entry_conditions) >= 6:
        warnings.append("조건이 과도하게 많아 샘플 수가 급감할 수 있습니다.")
    elif len(entry_conditions) >= 4:
        warnings.append("조건 수가 4개 이상입니다. 샘플 수 감소와 과최적화 위험을 확인하세요.")

    normalized_entries = []
    for condition in entry_conditions:
        result, normalized_condition = _validate_condition(condition, "entry_conditions")
        condition_results.append(result)
        normalized_entries.append(normalized_condition)
        if result["status"] == "auto_converted":
            warnings.append("문자열 조건을 객체형 조건으로 자동 변환했습니다. 시뮬레이션 전 조건을 확인하세요.")
    normalized["entry_conditions"] = normalized_entries

    if not isinstance(risk_filters, list):
        warnings.append("risk_filters는 배열이어야 합니다. 이번 검증에서는 빈 배열로 처리했습니다.")
        risk_filters = []
    normalized_risks = []
    for condition in risk_filters:
        result, normalized_condition = _validate_condition(condition, "risk_filters")
        if result["status"] == "auto_converted":
            warnings.append("문자열 위험 필터를 객체형 조건으로 자동 변환했습니다. action은 warning_only로 처리했습니다.")
        action = normalized_condition.get("action")
        if action and action not in SUPPORTED_RISK_ACTIONS:
            result["status"] = "unsupported_action"
            result["message"] = "지원하지 않는 위험 필터 action입니다."
        elif result["status"] in {"valid", "auto_converted"}:
            result["message"] = "위험 필터 조건으로 사용할 수 있습니다."
        risk_filter_results.append(result)
        normalized_risks.append(normalized_condition)
    normalized["risk_filters"] = normalized_risks

    add_buy_result, normalized_add_buy = _validate_add_buy_plan(add_buy_plan, risk_plan)
    normalized["add_buy_plan"] = normalized_add_buy
    warnings.extend(add_buy_result.get("warnings", []))

    status = _candidate_status(condition_results, risk_filter_results, add_buy_result, warnings, errors)
    auto_converted_count = sum(1 for item in [*condition_results, *risk_filter_results] if item["status"] == "auto_converted")
    structure_error_count = sum(1 for item in [*condition_results, *risk_filter_results] if item["status"] == "invalid_structure")
    return {
        "candidate_index": index,
        "scenario_name": scenario_name,
        "status": status,
        "status_label": STATUS_LABELS[status],
        "is_simulation_ready": status in {"simulation_ready", "risky"},
        "condition_results": condition_results,
        "risk_filter_results": risk_filter_results,
        "add_buy_result": add_buy_result,
        "warnings": warnings,
        "errors": errors,
        "normalized_candidate": normalized,
        "goal": goal,
        "auto_converted_count": auto_converted_count,
        "structure_error_count": structure_error_count,
    }


def _validate_condition(condition: Any, section: str) -> tuple[dict[str, Any], dict[str, Any]]:
    auto_converted = False
    original_condition = condition
    if isinstance(condition, str):
        converted = _parse_condition_string(condition, section)
        if converted is None:
            result = {
                "section": section,
                "indicator_key": None,
                "operator": None,
                "value": None,
                "status": "invalid_structure",
                "message": "문자열 조건입니다. indicator_key, operator, value가 분리된 객체형 조건이 필요합니다.",
                "original": condition,
            }
            return result, {"original": condition, "status": "convert_failed", "message": "지원하는 문자열 조건 패턴이 아닙니다."}
        normalized = converted
        auto_converted = True
    else:
        normalized = dict(condition) if isinstance(condition, dict) else {}
    indicator_key = normalized.get("indicator_key")
    operator = normalized.get("operator")
    value = normalized.get("value")
    result = {
        "section": section,
        "indicator_key": indicator_key,
        "operator": operator,
        "value": value,
        "status": "valid",
        "message": "계산 가능한 지표와 연산자입니다.",
    }

    if not isinstance(condition, dict):
        if not auto_converted:
            result.update({"status": "invalid_structure", "message": "조건은 객체 형식이어야 합니다."})
            return result, normalized
    if not indicator_key or not operator or "value" not in normalized:
        result.update({"status": "missing_field", "message": "indicator_key, operator, value가 필요합니다."})
        return result, normalized
    if indicator_key not in SUPPORTED_SCENARIO_INDICATORS:
        result.update({"status": "unsupported_indicator", "message": "현재 DrCT에서 지원하지 않는 지표입니다."})
        return result, normalized
    if operator not in SUPPORTED_OPERATORS:
        result.update({"status": "unsupported_operator", "message": "지원하지 않는 연산자입니다."})
        return result, normalized

    indicator = SUPPORTED_SCENARIO_INDICATORS[str(indicator_key)]
    if operator not in indicator["supported_operators"]:
        result.update({"status": "unsupported_operator", "message": "해당 지표에서 지원하지 않는 연산자입니다."})
        return result, normalized

    ok, normalized_value = _normalize_value(operator, value)
    if not ok:
        result.update({"status": "invalid_value", "message": "between은 숫자 2개 배열, 그 외 연산자는 숫자 값이 필요합니다."})
        return result, normalized

    normalized["value"] = normalized_value
    result["value"] = normalized_value
    if auto_converted:
        normalized["value"] = normalized_value
        result.update({
            "status": "auto_converted",
            "message": "문자열 조건을 객체형 조건으로 자동 변환했습니다. 시뮬레이션 전 확인하세요.",
            "original": original_condition,
        })
    return result, normalized


def _parse_condition_string(condition: str, section: str) -> dict[str, Any] | None:
    text = condition.strip()
    between_match = re.fullmatch(
        r"([A-Za-z_][A-Za-z0-9_]*)\s+between\s+(-?\d+(?:\.\d+)?)\s*(?:and|~)\s*(-?\d+(?:\.\d+)?)",
        text,
        flags=re.IGNORECASE,
    )
    if between_match:
        left = _to_number(between_match.group(2))
        right = _to_number(between_match.group(3))
        if left is None or right is None:
            return None
        converted = {
            "indicator_key": between_match.group(1),
            "operator": "between",
            "value": [left, right],
            "role": "auto_converted",
            "description": f"자동 변환된 조건: {text}",
        }
        if section == "risk_filters":
            converted["action"] = "warning_only"
            converted["reason"] = f"자동 변환된 위험 필터: {text}"
        return converted

    operator_match = re.fullmatch(
        r"([A-Za-z_][A-Za-z0-9_]*)\s*(>=|<=|>|<|=)\s*(-?\d+(?:\.\d+)?)",
        text,
    )
    if operator_match:
        value = _to_number(operator_match.group(3))
        if value is None:
            return None
        converted = {
            "indicator_key": operator_match.group(1),
            "operator": operator_match.group(2),
            "value": value,
            "role": "auto_converted",
            "description": f"자동 변환된 조건: {text}",
        }
        if section == "risk_filters":
            converted["action"] = "warning_only"
            converted["reason"] = f"자동 변환된 위험 필터: {text}"
        return converted

    return None


def _normalize_value(operator: str, value: Any) -> tuple[bool, Any]:
    if operator == "between":
        if not isinstance(value, list) or len(value) != 2:
            return False, value
        left = _to_number(value[0])
        right = _to_number(value[1])
        if left is None or right is None:
            return False, value
        return True, [left, right]
    number = _to_number(value)
    if number is None:
        return False, value
    return True, number


def _to_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any, default: int) -> int:
    number = _to_number(value)
    if number is None:
        return default
    return int(number)


def _validate_add_buy_plan(add_buy_plan: Any, risk_plan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    plan = dict(add_buy_plan) if isinstance(add_buy_plan, dict) else {}
    max_count = _to_int(plan.get("max_count", risk_plan.get("max_add_buy_count", 0)), 0)
    trigger_loss_pct = _to_number(plan.get("trigger_loss_pct", risk_plan.get("add_buy_trigger_loss_pct", -5)))
    amount_ratio = _to_number(plan.get("amount_ratio", 1.0))
    final_stop_loss_pct = _to_number(plan.get("final_stop_loss_pct", risk_plan.get("final_stop_loss_pct", -5)))
    normalized = {
        "enabled": bool(plan.get("enabled", risk_plan.get("add_buy_enabled", False))),
        "max_count": max_count,
        "trigger_basis": plan.get("trigger_basis") or "entry_price",
        "trigger_loss_pct": trigger_loss_pct if trigger_loss_pct is not None else -5,
        "amount_ratio": amount_ratio if amount_ratio is not None else 1.0,
        "stop_loss_basis": plan.get("stop_loss_basis") or risk_plan.get("final_stop_loss_basis") or "average_price",
        "final_stop_loss_pct": final_stop_loss_pct if final_stop_loss_pct is not None else -5,
    }
    warnings: list[str] = []
    errors: list[str] = []

    if not normalized["enabled"]:
        return {"status": "valid", "message": "추가매수를 사용하지 않는 전략입니다.", "warnings": []}, normalized

    if normalized["max_count"] > 2:
        errors.append("최대 추가매수 횟수는 0~2회까지만 허용합니다.")
    elif normalized["max_count"] == 2:
        warnings.append("추가매수 2회는 허용되지만 자금 부담과 과최적화 위험을 확인해야 합니다.")

    if normalized["trigger_basis"] not in SUPPORTED_PRICE_BASES:
        errors.append("지원하지 않는 추가매수 기준입니다.")
    if normalized["stop_loss_basis"] not in SUPPORTED_PRICE_BASES:
        errors.append("지원하지 않는 손절 기준입니다.")
    if trigger_loss_pct is None:
        errors.append("추가매수 트리거 손실률은 숫자여야 합니다.")
    if amount_ratio is None:
        errors.append("추가매수 금액 비율은 숫자여야 합니다.")
    if final_stop_loss_pct is None:
        errors.append("최종 손절률은 숫자여야 합니다.")

    trigger_loss = normalized["trigger_loss_pct"]
    if trigger_loss >= 0:
        errors.append("추가매수 트리거 손실률은 음수여야 합니다.")
    elif trigger_loss > -1:
        warnings.append("추가매수 트리거가 너무 민감합니다.")
    elif trigger_loss < -15:
        warnings.append("큰 하락 이후 추가매수하는 조건입니다. 손실 확대 위험을 확인하세요.")

    amount_ratio = normalized["amount_ratio"]
    if amount_ratio <= 0:
        errors.append("추가매수 금액 비율은 0보다 커야 합니다.")
    elif amount_ratio > 2:
        warnings.append("추가매수 금액이 1차 매수금액의 2배를 초과합니다.")

    final_stop = normalized["final_stop_loss_pct"]
    if final_stop >= 0:
        errors.append("최종 손절률은 음수여야 합니다.")
    elif final_stop <= -15:
        warnings.append("최종 손절률이 -15% 이하입니다. 실제 손실금액 확대 위험이 큽니다.")
    elif final_stop < -10 or final_stop > -3:
        warnings.append("최종 손절률은 보통 -3%~-10% 범위 안에서 재검토하는 것이 좋습니다.")

    if normalized["stop_loss_basis"] == "average_price":
        warnings.append("평균단가 기준 손절은 실제 손실금액을 키울 수 있습니다.")

    status = "invalid" if errors else "valid"
    message = "추가매수 전략을 사용할 수 있습니다." if status == "valid" else "추가매수 전략에 구조 오류가 있습니다."
    return {"status": status, "message": message, "warnings": warnings, "errors": errors}, normalized


def _candidate_status(
    condition_results: list[dict[str, Any]],
    risk_filter_results: list[dict[str, Any]],
    add_buy_result: dict[str, Any],
    warnings: list[str],
    errors: list[str],
) -> str:
    if (
        errors
        or add_buy_result.get("status") == "invalid"
        or any(item["status"] in {"missing_field", "invalid_value", "invalid_structure"} for item in condition_results)
        or any(item["status"] in {"invalid_structure"} for item in risk_filter_results)
    ):
        return "invalid"

    unsupported_conditions = [item for item in condition_results if item["status"] in {"unsupported_indicator", "unsupported_operator"}]
    if condition_results and len(unsupported_conditions) == len(condition_results):
        return "unsupported"
    if unsupported_conditions or any(item["status"] in {"unsupported_action", "unsupported_indicator", "unsupported_operator"} for item in risk_filter_results):
        return "needs_review"

    if warnings:
        return "risky"
    return "simulation_ready"
