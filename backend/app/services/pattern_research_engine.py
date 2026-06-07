from __future__ import annotations

import json
from statistics import mean
from typing import Any


SUPPORTED_DYNAMIC_EXECUTION_TYPES = {"distance_pct", "rolling_high"}
DEFAULT_OBSERVATION_INDICATORS = [
    "close_vs_ma20_pct",
    "close_vs_ma60_pct",
    "volume_ratio_20",
    "trading_value_ratio_20",
    "recent_3d_return",
    "recent_5d_return",
    "is_bullish",
    "close_above_previous_high",
]
BASE_FEATURE_KEYS = {
    "open_price",
    "high_price",
    "low_price",
    "close_price",
    "volume",
    "trading_value",
    "prev_volume",
    "volume_vs_prev_day",
    "prev_trading_value",
    "trading_value_vs_prev_day",
    "ma5",
    "ma10",
    "ma20",
    "ma60",
    "ma120",
    "ma60_5d_ago",
    "ma60_20d_ago",
    "ma60_slope_5d",
    "ma60_slope_20d",
    "is_ma60_rising_5d",
    "is_ma60_rising_20d",
    "close_vs_ma20_pct",
    "close_vs_ma60_pct",
    "volume_ma20",
    "volume_ratio_20",
    "trading_value_ma20",
    "trading_value_ratio_20",
    "return_1d",
    "return_3d",
    "return_5d",
    "recent_3d_return",
    "recent_5d_return",
    "is_bullish",
    "is_bearish",
    "close_above_previous_high",
    "close_between_ma10_ma20",
}


class DynamicIndicatorExecutionError(ValueError):
    def __init__(self, detail: dict[str, Any]) -> None:
        self.detail = detail
        super().__init__(str(detail.get("message") or "Unsupported dynamic indicator"))


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _avg(values: list[float | None]) -> float | None:
    valid = [value for value in values if value is not None]
    return round(mean(valid), 4) if valid else None


def _metric_average(samples: list[dict[str, Any]], key: str) -> float | None:
    values = [sample.get("features", {}).get(key) for sample in samples]
    valid = [value for value in values if value is not None]
    if not valid:
        return None
    if all(isinstance(value, bool) for value in valid):
        return round(sum(1 for value in valid if value) / len(valid) * 100, 2)
    return _avg([_num(value) for value in valid])


def _pct(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return ((current - previous) / previous) * 100


def _json_loads(value: Any, fallback: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value or ""))
    except (TypeError, json.JSONDecodeError):
        return fallback


def _normalize_dynamic_indicator_definition(raw: dict[str, Any]) -> dict[str, Any]:
    key = str(raw.get("indicator_key") or raw.get("suggested_indicator_key") or "").strip()
    calculation_type = str(raw.get("calculation_type") or "").strip()
    required = raw.get("required_indicators")
    if required is None:
        required = _json_loads(raw.get("required_indicators_json") or raw.get("required_columns_json"), [])
    required_indicators = [str(item).strip() for item in (required or []) if str(item).strip()]
    parameters = raw.get("parameters")
    if parameters is None:
        parameters = _json_loads(raw.get("parameters_json"), {})
    parameters = parameters if isinstance(parameters, dict) else {}
    if calculation_type == "distance_pct":
        if not parameters.get("target_indicator") and required_indicators:
            parameters["target_indicator"] = required_indicators[0]
        if not parameters.get("base_indicator") and len(required_indicators) >= 2:
            parameters["base_indicator"] = required_indicators[1]
        parameters.setdefault("unit", "%")
    if calculation_type == "rolling_high":
        if not parameters.get("target_indicator") and required_indicators:
            parameters["target_indicator"] = required_indicators[0]
        if not parameters.get("window"):
            parameters["window"] = 30
        parameters.setdefault("include_current_day", True)
    return {
        "indicator_key": key,
        "indicator_name": raw.get("indicator_name") or raw.get("suggested_indicator_name") or key,
        "calculation_type": calculation_type,
        "parameters": parameters,
        "required_indicators": required_indicators,
        "execution_supported": bool(raw.get("execution_supported", calculation_type in SUPPORTED_DYNAMIC_EXECUTION_TYPES)),
        "execution_status": raw.get("execution_status"),
        "execution_message": raw.get("execution_message"),
        "scope": raw.get("scope") or "registered",
    }


def validate_dynamic_indicator_execution(
    indicator_definition: dict[str, Any],
    available_indicator_keys: set[str] | None = None,
) -> dict[str, Any]:
    definition = _normalize_dynamic_indicator_definition(indicator_definition)
    calculation_type = definition.get("calculation_type")
    available = available_indicator_keys or BASE_FEATURE_KEYS
    if not definition.get("indicator_key"):
        return {
            "execution_supported": False,
            "execution_status": "invalid_parameters",
            "execution_message": "indicator_key가 비어 있습니다.",
        }
    if calculation_type not in SUPPORTED_DYNAMIC_EXECUTION_TYPES:
        return {
            "execution_supported": False,
            "execution_status": "needs_engine",
            "execution_message": f"{calculation_type or '-'} 계산 유형은 아직 샘플 실행 엔진에서 지원하지 않습니다.",
        }
    if calculation_type == "distance_pct":
        parameters = definition.get("parameters") or {}
        target_indicator = str(parameters.get("target_indicator") or "").strip()
        base_indicator = str(parameters.get("base_indicator") or "").strip()
        if not target_indicator or not base_indicator:
            return {
                "execution_supported": False,
                "execution_status": "invalid_parameters",
                "execution_message": "distance_pct에는 target_indicator와 base_indicator가 필요합니다.",
            }
        missing = [key for key in (target_indicator, base_indicator) if key not in available]
        if missing:
            return {
                "execution_supported": False,
                "execution_status": "missing_required_indicator",
                "execution_message": f"필요 지표가 샘플 feature에 없습니다: {', '.join(missing)}",
            }
    if calculation_type == "rolling_high":
        parameters = definition.get("parameters") or {}
        target_indicator = str(parameters.get("target_indicator") or "").strip()
        try:
            window = int(parameters.get("window") or 0)
        except (TypeError, ValueError):
            window = 0
        if not target_indicator:
            return {
                "execution_supported": False,
                "execution_status": "invalid_parameters",
                "execution_message": "rolling_high에는 target_indicator가 필요합니다.",
            }
        if window < 1:
            return {
                "execution_supported": False,
                "execution_status": "invalid_parameters",
                "execution_message": "rolling_high에는 1 이상의 window가 필요합니다.",
            }
        if target_indicator not in available:
            return {
                "execution_supported": False,
                "execution_status": "missing_required_indicator",
                "execution_message": f"필요 지표가 샘플 feature에 없습니다: {target_indicator}",
            }
    return {
        "execution_supported": True,
        "execution_status": "supported",
        "execution_message": f"{calculation_type} 계산 유형은 샘플 엔진에서 실행 가능합니다.",
    }


def compute_dynamic_indicator_for_features(features: dict[str, Any], indicator_definition: dict[str, Any]) -> Any:
    definition = _normalize_dynamic_indicator_definition(indicator_definition)
    if definition.get("calculation_type") != "distance_pct":
        return None
    parameters = definition.get("parameters") or {}
    target_value = _num(features.get(str(parameters.get("target_indicator") or "")))
    base_value = _num(features.get(str(parameters.get("base_indicator") or "")))
    if target_value is None or base_value is None or base_value == 0:
        return None
    return ((target_value - base_value) / base_value) * 100


def compute_dynamic_indicator_for_row(rows: list[dict[str, Any]], idx: int, features: dict[str, Any], indicator_definition: dict[str, Any]) -> Any:
    definition = _normalize_dynamic_indicator_definition(indicator_definition)
    calculation_type = definition.get("calculation_type")
    if calculation_type == "distance_pct":
        return compute_dynamic_indicator_for_features(features, definition)
    if calculation_type != "rolling_high":
        return None
    parameters = definition.get("parameters") or {}
    target_indicator = str(parameters.get("target_indicator") or "").strip()
    try:
        window = int(parameters.get("window") or 30)
    except (TypeError, ValueError):
        window = 30
    if not target_indicator or window < 1:
        return None
    start = max(0, idx - window + 1)
    values: list[float] = []
    for cursor in range(start, idx + 1):
        source_features = features if cursor == idx else _features(rows, cursor)
        value = _num(source_features.get(target_indicator))
        if value is not None:
            values.append(value)
    return max(values) if values else None


def _dynamic_indicator_definitions(parsed_goal: dict[str, Any]) -> dict[str, dict[str, Any]]:
    definitions: dict[str, dict[str, Any]] = {}
    raw_items = (
        list(parsed_goal.get("dynamic_indicators") or [])
        + list(parsed_goal.get("temporary_indicators") or [])
        + list(parsed_goal.get("unsupported_items") or [])
        + list(parsed_goal.get("new_indicator_candidates") or [])
    )
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        definition = _normalize_dynamic_indicator_definition(raw)
        key = str(definition.get("indicator_key") or "")
        if key:
            definitions[key] = definition
    return definitions


def _moving_average(rows: list[dict[str, Any]], idx: int, key: str, period: int) -> float | None:
    if idx + 1 < period:
        return None
    values = [_num(row.get(key)) for row in rows[idx - period + 1 : idx + 1]]
    if any(value is None for value in values):
        return None
    return sum(float(value) for value in values) / period


def _return_over(rows: list[dict[str, Any]], idx: int, days: int) -> float | None:
    if idx - days < 0:
        return None
    return _pct(_num(rows[idx].get("close_price")), _num(rows[idx - days].get("close_price")))


def _tags(features: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    close_vs_ma20 = features.get("close_vs_ma20_pct")
    volume_ratio = features.get("volume_ratio_20")
    trading_value_ratio = features.get("trading_value_ratio_20")
    recent_5d = features.get("recent_5d_return")
    if close_vs_ma20 is not None:
        if close_vs_ma20 > 3:
            tags.append("above_ma20")
        elif close_vs_ma20 < -3:
            tags.append("below_ma20")
        else:
            tags.append("near_ma20")
    if volume_ratio is not None and volume_ratio >= 1.5:
        tags.append("volume_spike")
    if trading_value_ratio is not None and trading_value_ratio >= 1.5:
        tags.append("trading_value_spike")
    if features.get("is_bullish"):
        tags.append("bullish_candle")
    if features.get("close_above_previous_high"):
        tags.append("close_above_previous_high")
    if recent_5d is not None and recent_5d < 0:
        tags.append("recent_pullback")
    if recent_5d is not None and recent_5d >= 10:
        tags.append("recent_surge")
    return tags


def _compare(value: Any, operator: str, expected: Any) -> bool:
    numeric = _num(value)
    if operator == "=":
        return bool(value) is bool(expected) if isinstance(expected, bool) else value == expected
    if numeric is None:
        return False
    if operator == ">":
        return numeric > float(expected)
    if operator == ">=":
        return numeric >= float(expected)
    if operator == "<":
        return numeric < float(expected)
    if operator == "<=":
        return numeric <= float(expected)
    if operator == "between" and isinstance(expected, list) and len(expected) == 2:
        return float(expected[0]) <= numeric <= float(expected[1])
    return False


def _condition_value(features: dict[str, Any], condition: dict[str, Any]) -> Any:
    indicator = str(condition.get("indicator") or condition.get("indicator_key") or "")
    if indicator == "close_price, ma20":
        close = features.get("close_price")
        ma20 = features.get("ma20")
        return None if close is None or ma20 is None else float(close) - float(ma20)
    return features.get(indicator)


def _condition_matched(features: dict[str, Any], condition: dict[str, Any]) -> bool:
    indicator = str(condition.get("indicator") or condition.get("indicator_key") or "")
    if indicator == "close_price, ma20":
        return features.get("close_price") is not None and features.get("ma20") is not None and float(features["close_price"]) > float(features["ma20"])
    return _compare(_condition_value(features, condition), str(condition.get("operator") or ""), condition.get("value"))


def _unique_keys(keys: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for key in keys:
        if key and key not in seen:
            seen.add(key)
            result.append(key)
    return result


def _observation_indicators(parsed_goal: dict[str, Any], dynamic_definitions: dict[str, dict[str, Any]]) -> list[str]:
    dynamic_keys = list(dynamic_definitions)
    condition_keys = [
        str(item.get("indicator") or item.get("indicator_key") or "")
        for item in list(parsed_goal.get("entry_filters") or []) + list(parsed_goal.get("exclude_filters") or [])
        if str(item.get("indicator") or item.get("indicator_key") or "") != "close_price, ma20"
    ]
    return _unique_keys(dynamic_keys + condition_keys + DEFAULT_OBSERVATION_INDICATORS)


def _condition_candidate_performance(
    samples: list[dict[str, Any]],
    conditions: list[dict[str, Any]],
    base_success_rate: float,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for condition in conditions:
        passed = [sample for sample in samples if _condition_matched(sample.get("features") or {}, condition)]
        success_count = sum(1 for sample in passed if sample.get("result_label") == "SUCCESS")
        failure_count = sum(1 for sample in passed if sample.get("result_label") == "FAILURE")
        success_rate = round(success_count / len(passed) * 100, 2) if passed else None
        results.append(
            {
                "condition_label": condition.get("label") or condition.get("source_text") or condition.get("natural_text") or "",
                "expression": condition.get("expression") or f"{condition.get('indicator_key') or condition.get('indicator')} {condition.get('operator')} {condition.get('value')}",
                "indicator_key": condition.get("indicator_key") or condition.get("indicator"),
                "passed_count": len(passed),
                "success_count": success_count,
                "failure_count": failure_count,
                "success_rate": success_rate,
                "lift_vs_base": round(success_rate - base_success_rate, 2) if success_rate is not None else None,
            }
        )
    return results


def _features(rows: list[dict[str, Any]], idx: int) -> dict[str, Any]:
    row = rows[idx]
    close = _num(row.get("close_price"))
    open_price = _num(row.get("open_price"))
    previous_close = _num(rows[idx - 1].get("close_price")) if idx > 0 else None
    previous_high = _num(rows[idx - 1].get("high_price")) if idx > 0 else None
    prev_volume = _num(rows[idx - 1].get("volume")) if idx > 0 else None
    prev_trading_value = _num(rows[idx - 1].get("trading_value")) if idx > 0 else None
    ma_values = {period: _moving_average(rows, idx, "close_price", period) for period in (5, 10, 20, 60, 120)}
    ma60_5d_ago = _moving_average(rows, idx - 5, "close_price", 60) if idx >= 5 else None
    ma60_20d_ago = _moving_average(rows, idx - 20, "close_price", 60) if idx >= 20 else None
    volume_ma20 = _moving_average(rows, idx, "volume", 20)
    trading_value_ma20 = _moving_average(rows, idx, "trading_value", 20)
    volume = _num(row.get("volume"))
    trading_value = _num(row.get("trading_value"))
    ma60_slope_5d = (ma_values[60] - ma60_5d_ago) if ma_values[60] is not None and ma60_5d_ago is not None else None
    ma60_slope_20d = (ma_values[60] - ma60_20d_ago) if ma_values[60] is not None and ma60_20d_ago is not None else None
    return {
        "open_price": open_price,
        "high_price": _num(row.get("high_price")),
        "low_price": _num(row.get("low_price")),
        "close_price": close,
        "volume": volume,
        "trading_value": trading_value,
        "prev_volume": prev_volume,
        "volume_vs_prev_day": (volume / prev_volume) if volume is not None and prev_volume else None,
        "prev_trading_value": prev_trading_value,
        "trading_value_vs_prev_day": (trading_value / prev_trading_value) if trading_value is not None and prev_trading_value else None,
        "ma5": ma_values[5],
        "ma10": ma_values[10],
        "ma20": ma_values[20],
        "ma60": ma_values[60],
        "ma120": ma_values[120],
        "ma60_5d_ago": ma60_5d_ago,
        "ma60_20d_ago": ma60_20d_ago,
        "ma60_slope_5d": ma60_slope_5d,
        "ma60_slope_20d": ma60_slope_20d,
        "is_ma60_rising_5d": bool(ma60_slope_5d is not None and ma60_slope_5d > 0),
        "is_ma60_rising_20d": bool(ma60_slope_20d is not None and ma60_slope_20d > 0),
        "close_vs_ma20_pct": _pct(close, ma_values[20]),
        "close_vs_ma60_pct": _pct(close, ma_values[60]),
        "volume_ma20": volume_ma20,
        "volume_ratio_20": (volume / volume_ma20) if volume is not None and volume_ma20 else None,
        "trading_value_ma20": trading_value_ma20,
        "trading_value_ratio_20": (trading_value / trading_value_ma20) if trading_value is not None and trading_value_ma20 else None,
        "return_1d": _pct(close, previous_close),
        "return_3d": _return_over(rows, idx, 3),
        "return_5d": _return_over(rows, idx, 5),
        "recent_3d_return": _return_over(rows, idx, 3),
        "recent_5d_return": _return_over(rows, idx, 5),
        "is_bullish": bool(close is not None and open_price is not None and close >= open_price),
        "is_bearish": bool(close is not None and open_price is not None and close < open_price),
        "close_above_previous_high": bool(close is not None and previous_high is not None and close > previous_high),
        "close_between_ma10_ma20": bool(
            close is not None
            and ma_values[10] is not None
            and ma_values[20] is not None
            and min(float(ma_values[10]), float(ma_values[20])) <= close <= max(float(ma_values[10]), float(ma_values[20]))
        ),
    }


def build_pattern_samples(
    rows: list[dict[str, Any]],
    stock: dict[str, Any],
    start_date: str,
    end_date: str,
    target_return_pct: float,
    target_days: int,
    stop_loss_pct: float,
    parsed_goal: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    parsed_goal = parsed_goal or {}
    entry_filters = list(parsed_goal.get("entry_filters") or [])
    exclude_filters = list(parsed_goal.get("exclude_filters") or [])
    reference_conditions = list(parsed_goal.get("reference_conditions") or [])
    applied_entry_filters = [item for item in entry_filters if item.get("apply_to_samples")]
    reference_entry_filters = [item for item in entry_filters if not item.get("apply_to_samples")] + reference_conditions
    applied_exclude_filters = [item for item in exclude_filters if item.get("apply_to_samples")]
    dynamic_definitions = _dynamic_indicator_definitions(parsed_goal)
    applied_conditions = applied_entry_filters + applied_exclude_filters
    for condition in applied_conditions:
        indicator_key = str(condition.get("indicator") or condition.get("indicator_key") or "")
        if indicator_key == "close_price, ma20" or indicator_key in BASE_FEATURE_KEYS:
            continue
        definition = dynamic_definitions.get(indicator_key)
        if not definition:
            raise DynamicIndicatorExecutionError(
                {
                    "error_code": "UNSUPPORTED_DYNAMIC_INDICATOR",
                    "message": f"신규 지표 {indicator_key}의 실행 정의가 없어 샘플 생성 엔진에서 계산할 수 없습니다.",
                    "indicator_key": indicator_key,
                    "calculation_type": "",
                    "required_action": "지표 기준정보 등록 또는 이번 연구에서만 사용 처리가 필요합니다.",
                }
            )
        execution = validate_dynamic_indicator_execution(definition, BASE_FEATURE_KEYS)
        if not execution.get("execution_supported"):
            raise DynamicIndicatorExecutionError(
                {
                    "error_code": "UNSUPPORTED_DYNAMIC_INDICATOR",
                    "message": execution.get("execution_message") or f"신규 지표 {indicator_key}를 샘플 생성 엔진에서 계산할 수 없습니다.",
                    "indicator_key": indicator_key,
                    "calculation_type": definition.get("calculation_type"),
                    "required_action": "지원되는 calculation_type인지 확인하거나 지표 계산 엔진 연결이 필요합니다.",
                }
            )
    total_raw_candidate_days = 0
    total_after_entry_filters = 0
    total_after_exclude_filters = 0
    for idx, row in enumerate(rows):
        trade_date = str(row.get("trade_date"))
        if trade_date < start_date or trade_date > end_date:
            continue
        future_rows = rows[idx + 1 : idx + 1 + target_days]
        if len(future_rows) < target_days:
            continue
        entry = _num(row.get("close_price"))
        if not entry:
            continue
        total_raw_candidate_days += 1
        features = _features(rows, idx)
        for indicator_key, definition in dynamic_definitions.items():
            execution = validate_dynamic_indicator_execution(definition, set(features.keys()) | BASE_FEATURE_KEYS)
            if execution.get("execution_supported"):
                features[indicator_key] = compute_dynamic_indicator_for_row(rows, idx, features, definition)
        matched_conditions: list[str] = []
        failed_conditions: list[str] = []
        for condition in entry_filters:
            expression = str(condition.get("expression") or condition.get("label") or "")
            if _condition_matched(features, condition):
                matched_conditions.append(expression)
            else:
                failed_conditions.append(expression)
        if applied_entry_filters and any(not _condition_matched(features, condition) for condition in applied_entry_filters):
            continue
        total_after_entry_filters += 1
        exclude_reason = ""
        for condition in applied_exclude_filters:
            if _condition_matched(features, condition):
                exclude_reason = str(condition.get("expression") or condition.get("label") or "제외 조건")
                break
        if exclude_reason:
            continue
        total_after_exclude_filters += 1
        future_highs = [_num(item.get("high_price")) for item in future_rows]
        future_lows = [_num(item.get("low_price")) for item in future_rows]
        future_close = _num(future_rows[-1].get("close_price"))
        if any(value is None for value in future_highs + future_lows) or future_close is None:
            continue
        max_future_return = ((max(float(v) for v in future_highs) - entry) / entry) * 100
        min_future_return = ((min(float(v) for v in future_lows) - entry) / entry) * 100
        future_return = ((future_close - entry) / entry) * 100
        target_hit = max_future_return >= target_return_pct
        stop_hit = min_future_return <= stop_loss_pct
        if stop_hit:
            label = "FAILURE"
        elif target_hit:
            label = "SUCCESS"
        else:
            label = "FAILURE"
        features["is_entry_candidate"] = True
        features["exclude_reason"] = ""
        features["matched_conditions"] = matched_conditions
        features["failed_conditions"] = failed_conditions
        samples.append(
            {
                "stock_code": stock["stock_code"],
                "stock_name": stock.get("stock_name"),
                "trade_date": trade_date,
                "entry_price": entry,
                "max_future_return_pct": round(max_future_return, 4),
                "min_future_return_pct": round(min_future_return, 4),
                "future_return_pct": round(future_return, 4),
                "target_hit": 1 if target_hit else 0,
                "stop_hit": 1 if stop_hit else 0,
                "result_label": label,
                "features": features,
                "pattern_tags": _tags(features),
            }
        )
    observation_indicators = _observation_indicators(parsed_goal, dynamic_definitions)
    summary = summarize_samples(samples, observation_indicators)
    return samples, {
        **summary,
        "applied_success_criteria": parsed_goal.get("success_criteria") or parsed_goal.get("success_rule") or {},
        "applied_failure_criteria": parsed_goal.get("failure_criteria") or parsed_goal.get("failure_rule") or {},
        "applied_entry_filters": applied_entry_filters,
        "reference_entry_filters": reference_entry_filters,
        "applied_exclude_filters": applied_exclude_filters,
        "dynamic_indicators": list(dynamic_definitions.values()),
        "observation_indicators": observation_indicators,
        "condition_candidate_performance": _condition_candidate_performance(
            samples,
            [item for item in reference_entry_filters + applied_entry_filters + applied_exclude_filters if item.get("indicator_key") or item.get("indicator")],
            float(summary.get("success_rate") or 0),
        ),
        "sample_filter_warning": "적용 조건이 너무 엄격하여 샘플 수가 20건 미만입니다. 일부 조건을 조건 후보로 전환하는 것을 검토하세요." if len(samples) < 20 else "",
        "total_raw_candidate_days": total_raw_candidate_days,
        "total_after_entry_filters": total_after_entry_filters,
        "total_after_exclude_filters": total_after_exclude_filters,
    }


def summarize_samples(samples: list[dict[str, Any]], observation_indicators: list[str] | None = None) -> dict[str, Any]:
    total = len(samples)
    success = [sample for sample in samples if sample["result_label"] == "SUCCESS"]
    failure = [sample for sample in samples if sample["result_label"] == "FAILURE"]
    neutral = [sample for sample in samples if sample["result_label"] == "NEUTRAL"]
    keys = observation_indicators or DEFAULT_OBSERVATION_INDICATORS
    avg_success = {key: _metric_average(success, key) for key in keys}
    avg_failure = {key: _metric_average(failure, key) for key in keys}
    differences = {
        key: round(float(avg_success[key]) - float(avg_failure[key]), 4)
        if avg_success.get(key) is not None and avg_failure.get(key) is not None
        else None
        for key in set(avg_success) | set(avg_failure)
    }
    return {
        "total_samples": total,
        "success_count": len(success),
        "failure_count": len(failure),
        "neutral_count": len(neutral),
        "success_rate": round(len(success) / total * 100, 2) if total else 0,
        "failure_rate": round(len(failure) / total * 100, 2) if total else 0,
        "avg_success": avg_success,
        "avg_failure": avg_failure,
        "differences": differences,
    }
