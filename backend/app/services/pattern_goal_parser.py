from __future__ import annotations

import re
from typing import Any


def _normalize_percent_text(text: str) -> str:
    return text.replace("프로", "%").replace("퍼센트", "%")


def _extract_target_days(text: str) -> tuple[int, list[str]]:
    warnings: list[str] = []
    patterns = [
        (r"(\d+)\s*거래일\s*(?:안에|이내|내|동안)?", lambda value: int(value)),
        (r"(\d+)\s*일\s*(?:안에|이내|내)", lambda value: int(value)),
        (r"2\s*주일\s*(?:안에|이내|내)", lambda _value: 10),
        (r"2\s*주\s*(?:안에|이내|내)", lambda _value: 10),
        (r"(?:1\s*)?주일\s*(?:안에|이내|내)", lambda _value: 5),
        (r"1\s*주\s*(?:안에|이내|내)", lambda _value: 5),
        (r"일주일\s*(?:안에|이내|내)", lambda _value: 5),
        (r"한\s*달\s*(?:안에|이내|내)", lambda _value: 20),
        (r"1\s*개월\s*(?:안에|이내|내)", lambda _value: 20),
    ]
    for pattern, converter in patterns:
        match = re.search(pattern, text)
        if match:
            return max(1, converter(match.group(1) if match.groups() else "")), warnings
    if re.search(r"\d+\s*일선|\d+\s*일\s*이동평균|이평선|이동평균선", text):
        warnings.append("이동평균선의 숫자는 목표 기간으로 해석하지 않았습니다. 명시 기간이 없어 기본 5거래일을 적용했습니다.")
    return 5, warnings


def _extract_target_return(text: str) -> float:
    normalized = _normalize_percent_text(text)
    patterns = [
        r"(\d+(?:\.\d+)?)\s*%\s*(?:이상\s*)?상승",
        r"수익률\s*(\d+(?:\.\d+)?)\s*%",
        r"목표\s*(\d+(?:\.\d+)?)\s*%",
        r"\+(\d+(?:\.\d+)?)\s*%",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            return float(match.group(1))
    return 5.0


def _extract_stop_loss(text: str) -> float:
    normalized = _normalize_percent_text(text)
    patterns = [
        r"손절[^\d\-]*(?:-)?(\d+(?:\.\d+)?)\s*%",
        r"손실[^\d\-]*(?:-)?(\d+(?:\.\d+)?)\s*%",
        r"-(\d+(?:\.\d+)?)\s*%\s*이내",
        r"(\d+(?:\.\d+)?)\s*%\s*손절",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            return -abs(float(match.group(1)))
    return -5.0


def _condition(
    *,
    source_text: str,
    label: str,
    indicator: str,
    operator: str,
    expression: str,
    value: Any = None,
    apply_to_samples: bool,
    status: str,
    source: str = "rule_base",
) -> dict[str, Any]:
    item = {
        "source_text": source_text,
        "natural_text": source_text,
        "label": label,
        "indicator": indicator,
        "indicator_key": indicator,
        "operator": operator,
        "expression": expression,
        "apply_to_samples": apply_to_samples,
        "status": status,
        "source": source,
    }
    if value is not None:
        item["value"] = value
    return item


class PatternGoalParser:
    def parse(self, goal_text: str) -> dict[str, Any]:
        text = re.sub(r"\s+", " ", goal_text.strip())
        target_days, warnings = _extract_target_days(text)
        target_return_pct = _extract_target_return(text)
        stop_loss_pct = _extract_stop_loss(text)

        success_criteria = {
            "source_text": f"{target_days}거래일 안에 {target_return_pct:g}% 이상 상승",
            "target_return_pct": target_return_pct,
            "target_days": target_days,
            "price_basis": "high",
            "expression": f"max_future_return_{target_days}d >= {target_return_pct:g}",
            "apply_to_samples": True,
            "status": "applied",
            "source": "rule_base",
        }
        failure_criteria = {
            "source_text": f"손절 {stop_loss_pct:g}% 이내",
            "stop_loss_pct": stop_loss_pct,
            "target_days": target_days,
            "price_basis": "low",
            "target_fail_is_failure": True,
            "expression": f"min_future_return_{target_days}d <= {stop_loss_pct:g}",
            "apply_to_samples": True,
            "status": "applied",
            "source": "rule_base",
        }

        entry_filters: list[dict[str, Any]] = []
        exclude_filters: list[dict[str, Any]] = []
        unsupported_items: list[dict[str, Any]] = []
        temporary_indicators: list[dict[str, Any]] = []
        indicator_candidates = [
            f"max_future_return_{target_days}d",
            f"min_future_return_{target_days}d",
            f"future_return_{target_days}d",
        ]

        def add_entry(condition: dict[str, Any]) -> None:
            entry_filters.append(condition)
            for part in str(condition["indicator"]).split(","):
                key = part.strip()
                if key and key not in indicator_candidates:
                    indicator_candidates.append(key)

        if re.search(r"20\s*일선\s*근처|20\s*일선.*눌림|눌림|눌림목", text):
            add_entry(
                _condition(
                    source_text="20일선 근처",
                    label="20일선 근처 눌림",
                    indicator="close_vs_ma20_pct",
                    operator="between",
                    value=[-3, 3],
                    expression="-3 <= close_vs_ma20_pct <= 3",
                    apply_to_samples=False,
                    status="needs_review",
                )
            )
            indicator_candidates.extend(["ma20", "recent_5d_return"])
        if re.search(r"5\s*일선.*10\s*일선|5\s*일\s*이동평균.*10\s*일\s*이동평균|5\s*일선.*근처|10\s*일선.*근처", text):
            add_entry(
                _condition(
                    source_text="5일선이 10일선 근처",
                    label="5일선-10일선 이격률",
                    indicator="ma5_vs_ma10_pct",
                    operator="between",
                    value=[-3, 3],
                    expression="-3 <= ma5_vs_ma10_pct <= 3",
                    apply_to_samples=False,
                    status="needs_review",
                    source="rule_base_candidate",
                )
            )
            temporary_indicators.append(
                {
                    "indicator_key": "ma5_vs_ma10_pct",
                    "indicator_name": "5일선과 10일선 이격률",
                    "calculation_type": "distance_pct",
                    "parameters": {
                        "target_indicator": "ma5",
                        "base_indicator": "ma10",
                        "unit": "%",
                    },
                    "required_indicators": ["ma5", "ma10"],
                    "execution_supported": True,
                    "execution_status": "supported",
                    "execution_message": "distance_pct 계산 유형은 샘플 엔진에서 실행 가능합니다.",
                    "scope": "run_only",
                }
            )
            indicator_candidates.extend(["ma5", "ma10", "ma5_vs_ma10_pct"])
        if re.search(r"종가(?:는|가)?\s*20\s*일선\s*위|20\s*일선\s*위", text):
            add_entry(
                _condition(
                    source_text="종가는 20일선 위",
                    label="종가 20일선 위",
                    indicator="close_price, ma20",
                    operator=">",
                    expression="close_price > ma20",
                    apply_to_samples=True,
                    status="applied",
                )
            )
        if re.search(r"60\s*일선.*상승|60\s*일\s*이동평균.*상승", text):
            add_entry(
                _condition(
                    source_text="60일선은 상승추세",
                    label="60일선 상승추세",
                    indicator="ma60_slope_5d",
                    operator=">",
                    value=0,
                    expression="ma60_slope_5d > 0",
                    apply_to_samples=True,
                    status="needs_review",
                )
            )
            indicator_candidates.extend(["ma60", "ma60_slope_5d", "is_ma60_rising_5d"])
        volume_prev_match = re.search(r"거래량.*전날(?:의)?\s*(\d+(?:\.\d+)?)\s*배", text)
        if volume_prev_match:
            value = float(volume_prev_match.group(1))
            add_entry(
                _condition(
                    source_text=f"거래량은 전날의 {value:g}배",
                    label="거래량 전일 대비 증가",
                    indicator="volume_vs_prev_day",
                    operator=">=",
                    value=value,
                    expression=f"volume_vs_prev_day >= {value:g}",
                    apply_to_samples=True,
                    status="applied",
                )
            )
        elif "거래량" in text and not re.search(r"거래량\s*(?:은|이)?\s*\d+(?:\.\d+)?\s*배", text):
            add_entry(
                _condition(
                    source_text="거래량 증가",
                    label="거래량 20일 평균 대비 증가",
                    indicator="volume_ratio_20",
                    operator=">=",
                    value=1.3,
                    expression="volume_ratio_20 >= 1.3",
                    apply_to_samples=False,
                    status="needs_review",
                )
            )
        if "거래대금" in text:
            add_entry(
                _condition(
                    source_text="거래대금이 다시 유입",
                    label="거래대금 20일 평균 대비 증가",
                    indicator="trading_value_ratio_20",
                    operator=">=",
                    value=1.3,
                    expression="trading_value_ratio_20 >= 1.3",
                    apply_to_samples=False,
                    status="needs_review",
                )
            )
        if "전일 고가" in text:
            add_entry(
                _condition(
                    source_text="전일 고가 돌파",
                    label="전일 고가 돌파",
                    indicator="close_above_previous_high",
                    operator="=",
                    value=True,
                    expression="close_above_previous_high = true",
                    apply_to_samples=True,
                    status="applied",
                )
            )

        if any(keyword in text for keyword in ("추격매수 제외", "급등 직후 제외", "급등 직후")):
            exclude_filters.append(
                {
                    "source_text": "급등 직후 추격매수 제외",
                    "natural_text": "급등 직후 추격매수 제외",
                    "label": "급등 직후 제외",
                    "indicator": "recent_3d_return",
                    "indicator_key": "recent_3d_return",
                    "operator": ">=",
                    "value": 15,
                    "expression": "recent_3d_return >= 15",
                    "exclude_when_true": True,
                    "apply_to_samples": True,
                    "status": "needs_review",
                    "source": "rule_base",
                }
            )
            indicator_candidates.append("recent_3d_return")
        rapid_candle_match = re.search(
            r"(?P<window>\d+)\s*일\s*(?:안에|이내|내|동안)?[^\n。.!?]*?(?P<return>\d+(?:\.\d+)?)\s*%\s*이상\s*급등.*?(?:캔들|봉)?",
            _normalize_percent_text(text),
        )
        if rapid_candle_match:
            window = int(rapid_candle_match.group("window"))
            return_pct = float(rapid_candle_match.group("return"))
            source_text = f"{window}일 내에 {return_pct:g}% 이상 급등한 캔들이 있다"
            add_entry(
                _condition(
                    source_text=source_text,
                    label=f"최근 {window}일 급등 캔들 존재",
                    indicator=f"max_return_1d_{window}d",
                    operator=">=",
                    value=return_pct,
                    expression=f"max_return_1d_{window}d >= {return_pct:g}",
                    apply_to_samples=False,
                    status="needs_review",
                    source="rule_base_candidate",
                )
            )
            unsupported_items.append(
                {
                    "source_text": source_text,
                    "natural_text": source_text,
                    "reason": f"최근 {window}거래일 동안 일간 수익률 {return_pct:g}% 이상 캔들이 있었는지 확인하는 수식 후보입니다.",
                    "indicator_key": f"max_return_1d_{window}d",
                    "indicator_name": f"최근 {window}일 최대 일간수익률",
                    "expression": f"max_return_1d_{window}d >= {return_pct:g}",
                    "calculation_type": "rolling_high",
                    "required_indicators": ["return_1d"],
                    "parameters": {
                        "target_indicator": "return_1d",
                        "window": window,
                        "unit": "%",
                    },
                    "status": "needs_review",
                    "display_group": "formula_required",
                }
            )
            indicator_candidates.extend(["return_1d", f"max_return_1d_{window}d"])
        if any(keyword in text for keyword in ("세력", "주도주 느낌", "수급")):
            unsupported_items.append({"source_text": "세력/수급/주도주 느낌", "reason": "현재 보유 데이터만으로 직접 계산하기 어려움"})

        interpreted_items = [
            {"category": "success_criteria", "natural_text": success_criteria["source_text"], "expression": success_criteria["expression"], "status": "applied", "source": "rule_base"},
            {"category": "failure_criteria", "natural_text": failure_criteria["source_text"], "expression": failure_criteria["expression"], "status": "applied", "source": "rule_base"},
            *[
                {"category": "entry_filter", "natural_text": item["source_text"], "expression": item["expression"], "indicator_key": item["indicator"], "status": item["status"], "source": item.get("source", "rule_base")}
                for item in entry_filters
            ],
            *[
                {"category": "exclude_filter", "natural_text": item["source_text"], "expression": item["expression"], "indicator_key": item["indicator"], "status": item["status"], "source": item.get("source", "rule_base")}
                for item in exclude_filters
            ],
        ]

        parsed_goal = {
            "goal_text": text,
            "success_criteria": success_criteria,
            "failure_criteria": failure_criteria,
            "success_rule": success_criteria,
            "failure_rule": failure_criteria,
            "target_return_pct": target_return_pct,
            "target_days": target_days,
            "stop_loss_pct": stop_loss_pct,
            "max_holding_days": target_days,
            "success_price_basis": "high",
            "failure_price_basis": "low",
            "entry_filters": entry_filters,
            "exclude_filters": exclude_filters,
            "hypothesis_conditions": entry_filters + exclude_filters,
            "indicator_candidates": list(dict.fromkeys(indicator_candidates)),
            "temporary_indicators": temporary_indicators,
            "unsupported_items": unsupported_items,
            "warnings": warnings,
        }
        return {
            "parsed_goal": parsed_goal,
            "interpreted_items": interpreted_items,
            "entry_filters": entry_filters,
            "exclude_filters": exclude_filters,
            "needs_review_items": [item for item in entry_filters + exclude_filters if item.get("status") == "needs_review"],
            "unsupported_items": unsupported_items,
            "warnings": warnings,
        }
