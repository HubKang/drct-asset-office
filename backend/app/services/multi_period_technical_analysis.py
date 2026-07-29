from __future__ import annotations

from datetime import datetime, timedelta
import math
from statistics import fmean
from time import perf_counter
from typing import Any

from backend.app.services.technical_analysis_service import (
    DISPLAY_PERIOD_DAYS,
    PERIOD_PROFILES,
    TECHNICAL_PERIODS,
    calculate_regression_channel,
    calculate_technical_analysis,
    normalize_configuration,
)


DIRECTION_LABELS = {
    "UP": "상승",
    "DOWN": "하락",
    "SIDEWAYS": "횡보",
    "UNCLEAR": "방향성 불명확",
    "INSUFFICIENT": "데이터 부족",
}
TREND_LABELS = {
    "UP_TREND": "상승 추세",
    "DOWN_TREND": "하락 추세",
    "SIDEWAYS": "횡보",
    "INSUFFICIENT": "데이터 부족",
}
STATE_LABELS = {
    "INSUFFICIENT": "데이터 부족",
    "SIDEWAYS": "횡보",
    "TREND_ESTABLISHED": "추세 확정",
    "TREND_MAINTAINED": "추세 유지",
    "TREND_WEAKENING": "추세 약화",
    "BREAK_CANDIDATE": "추세 이탈 후보",
    "BREAK_CONFIRMED": "추세 이탈 확인",
    "FALSE_BREAK_RECOVERED": "일시 이탈 후 복귀",
    "REVERSAL_CANDIDATE": "반전 후보",
    "REVERSAL_CONFIRMED": "반전 확인",
    "TREND_RESUMED": "기존 추세 재개",
}
EVENT_STATES = {
    "TREND_ESTABLISHED",
    "TREND_WEAKENING",
    "BREAK_CANDIDATE",
    "BREAK_CONFIRMED",
    "FALSE_BREAK_RECOVERED",
    "REVERSAL_CONFIRMED",
    "TREND_RESUMED",
}


def _number(value: Any) -> float:
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else 0.0
    except (TypeError, ValueError):
        return 0.0


def _rounded(value: float | None, digits: int = 6) -> float | None:
    return None if value is None or not math.isfinite(value) else round(value, digits)


def _clean_rows(rows: list[dict[str, Any]], as_of_date: str) -> list[dict[str, Any]]:
    return sorted(
        (
            dict(row)
            for row in rows
            if str(row.get("trade_date") or "") <= as_of_date
            and _number(row.get("close_price")) > 0
        ),
        key=lambda row: str(row["trade_date"]),
    )


def _period_rows(rows: list[dict[str, Any]], as_of_date: str, period: str) -> list[dict[str, Any]]:
    if period == "ALL":
        return rows
    cutoff = (
        datetime.strptime(as_of_date, "%Y-%m-%d").date()
        - timedelta(days=DISPLAY_PERIOD_DAYS[period])
    ).isoformat()
    return [row for row in rows if str(row["trade_date"]) >= cutoff]


def _classify_direction(core: dict[str, float | None], config: dict[str, Any]) -> str:
    normalized = float(core.get("normalized_slope") or 0)
    r_squared = float(core.get("r_squared") or 0)
    if r_squared < float(config["minimum_r_squared"]):
        return "UNCLEAR"
    if abs(normalized) < float(config["minimum_trend_strength"]):
        return "SIDEWAYS"
    return "UP" if normalized > 0 else "DOWN"


def _trend_direction(direction: str | None) -> str:
    if direction == "UP":
        return "UP_TREND"
    if direction == "DOWN":
        return "DOWN_TREND"
    if direction in {"SIDEWAYS", "UNCLEAR"}:
        return "SIDEWAYS"
    return "INSUFFICIENT"


def _channel_position_label(value: float | None) -> str:
    if value is None:
        return "판정 보류"
    if value < 0:
        return "채널 하단 이탈"
    if value <= 0.25:
        return "하단 부근"
    if value < 0.75:
        return "중앙 부근"
    if value <= 1:
        return "상단 부근"
    return "채널 상단 이탈"


def _event_reason(state: str, direction: str, channel_position: float | None) -> str:
    if state == "REVERSAL_CONFIRMED":
        return f"{DIRECTION_LABELS.get(direction, direction)} 방향 기울기가 지속되어 반전을 확인했습니다."
    if state == "BREAK_CONFIRMED":
        return "회귀 채널 반대편 이탈이 설정 봉 수 이상 지속되었습니다."
    if state == "BREAK_CANDIDATE":
        return "현재가가 회귀 채널 반대편을 벗어나 지속 여부를 확인 중입니다."
    if state == "FALSE_BREAK_RECOVERED":
        return "채널을 일시적으로 이탈한 뒤 기존 추세 범위로 복귀했습니다."
    if state == "TREND_RESUMED":
        return "약화 구간 이후 기존 방향의 기울기가 다시 확인되었습니다."
    if state == "TREND_WEAKENING":
        return "기울기 또는 회귀 적합도가 약해져 추세 강도가 낮아졌습니다."
    if channel_position is not None:
        return f"현재 채널 위치는 {_channel_position_label(channel_position)}입니다."
    return "기울기와 지속 조건을 충족해 추세가 확정되었습니다."


def calculate_trend_state_series(
    rows: list[dict[str, Any]],
    *,
    configuration: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a causal trend-state series. Every point uses only its own prefix."""
    config = normalize_configuration(configuration)
    selected_profile = dict(profile or PERIOD_PROFILES["6M"])
    window = int(selected_profile["current_window"])
    minimum = int(selected_profile["minimum_observations"])
    evaluation_minimum = max(6, min(12, minimum))
    direction_persistence = int(selected_profile["direction_persistence"])
    break_persistence = int(selected_profile["break_persistence"])

    confirmed_direction: str | None = None
    direction_candidate: str | None = None
    direction_candidate_count = 0
    direction_candidate_start_index: int | None = None
    break_count = 0
    trend_start_date: str | None = None
    trend_start_index: int | None = None
    previous_state = "INSUFFICIENT"
    points: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []

    for index, row in enumerate(rows):
        observation_date = str(row["trade_date"])
        sample_rows = rows[max(0, index - window + 1): index + 1]
        values = [_number(item["close_price"]) for item in sample_rows]
        if len(values) < evaluation_minimum:
            points.append({
                "observation_date": observation_date,
                "direction": "INSUFFICIENT",
                "transition_state": "INSUFFICIENT",
                "slope": None,
                "normalized_slope": None,
                "r_squared": None,
                "channel_position": None,
                "trend_strength": None,
                "persistence_count": 0,
                "trend_start_date": None,
            })
            continue

        core = calculate_regression_channel(values, float(config["channel_multiplier"]))
        raw_direction = _classify_direction(core, config)
        directional = raw_direction if raw_direction in {"UP", "DOWN"} else None
        state = "TREND_MAINTAINED"
        direction_changed = False

        if confirmed_direction is None:
            if directional is None:
                state = "SIDEWAYS"
            else:
                if direction_candidate == directional:
                    direction_candidate_count += 1
                else:
                    direction_candidate = directional
                    direction_candidate_count = 1
                    direction_candidate_start_index = index
                if direction_candidate_count >= direction_persistence:
                    confirmed_direction = directional
                    trend_start_index = direction_candidate_start_index if direction_candidate_start_index is not None else index
                    trend_start_date = str(rows[trend_start_index]["trade_date"])
                    direction_changed = True
                    state = "TREND_ESTABLISHED"
                else:
                    state = "REVERSAL_CANDIDATE"
        elif directional is not None and directional != confirmed_direction:
            if direction_candidate == directional:
                direction_candidate_count += 1
            else:
                direction_candidate = directional
                direction_candidate_count = 1
                direction_candidate_start_index = index
            state = "REVERSAL_CANDIDATE"
            if direction_candidate_count >= direction_persistence:
                confirmed_direction = directional
                trend_start_index = direction_candidate_start_index if direction_candidate_start_index is not None else index
                trend_start_date = str(rows[trend_start_index]["trade_date"])
                direction_candidate = None
                direction_candidate_count = 0
                direction_candidate_start_index = None
                break_count = 0
                direction_changed = True
                state = "REVERSAL_CONFIRMED"
        else:
            direction_candidate = None
            direction_candidate_count = 0
            direction_candidate_start_index = None
            if directional is None:
                state = "TREND_WEAKENING"
            elif previous_state in {"TREND_WEAKENING", "BREAK_CANDIDATE", "BREAK_CONFIRMED"}:
                state = "TREND_RESUMED"

        channel_position = (
            float(core["channel_position"])
            if core.get("channel_position") is not None
            else None
        )
        opposite_break = (
            not direction_changed
            and confirmed_direction in {"UP", "DOWN"}
            and channel_position is not None
            and (
                (confirmed_direction == "UP" and channel_position < 0)
                or (confirmed_direction == "DOWN" and channel_position > 1)
            )
        )
        if opposite_break:
            break_count += 1
            state = "BREAK_CONFIRMED" if break_count >= break_persistence else "BREAK_CANDIDATE"
        else:
            if (
                not direction_changed
                and previous_state in {"BREAK_CANDIDATE", "BREAK_CONFIRMED"}
                and directional == confirmed_direction
            ):
                state = "FALSE_BREAK_RECOVERED"
            break_count = 0

        persistence_count = (
            index - trend_start_index + 1
            if trend_start_index is not None
            else 0
        )
        trend_direction = _trend_direction(confirmed_direction or raw_direction)
        point = {
            "observation_date": observation_date,
            "direction": trend_direction,
            "transition_state": state,
            "slope": _rounded(float(core["slope"]), 8),
            "normalized_slope": _rounded(float(core["normalized_slope"])),
            "r_squared": _rounded(float(core["r_squared"])),
            "channel_position": _rounded(channel_position),
            "trend_strength": _rounded(min(100.0, float(core["trend_strength"]) * 4), 2),
            "persistence_count": persistence_count,
            "trend_start_date": trend_start_date,
        }
        points.append(point)

        if state != previous_state and state in EVENT_STATES:
            events.append({
                "observation_date": observation_date,
                "previous_state": previous_state,
                "previous_state_label": STATE_LABELS.get(previous_state, previous_state),
                "current_state": state,
                "current_state_label": STATE_LABELS.get(state, state),
                "direction": trend_direction,
                "direction_label": TREND_LABELS.get(trend_direction, trend_direction),
                "reason": _event_reason(state, raw_direction, channel_position),
                "trend_strength": point["trend_strength"],
                "channel_position": point["channel_position"],
            })
        previous_state = state

    return {"points": points, "events": events, "current": points[-1] if points else None}


def _period_direction(
    rows: list[dict[str, Any]],
    config: dict[str, Any],
    minimum_observations: int,
) -> dict[str, Any]:
    if len(rows) < minimum_observations:
        return {
            "direction": "INSUFFICIENT",
            "direction_label": "데이터 부족",
            "slope": None,
            "normalized_slope": None,
            "r_squared": None,
            "trend_strength": None,
            "channel_position": None,
            "channel_position_label": "데이터 부족",
        }
    core = calculate_regression_channel(
        [_number(row["close_price"]) for row in rows],
        float(config["channel_multiplier"]),
    )
    direction = _classify_direction(core, config)
    return {
        "direction": direction,
        "direction_label": DIRECTION_LABELS[direction],
        "slope": _rounded(float(core["slope"]), 8),
        "normalized_slope": _rounded(float(core["normalized_slope"])),
        "r_squared": _rounded(float(core["r_squared"])),
        "trend_strength": _rounded(min(100.0, float(core["trend_strength"]) * 4), 2),
        "channel_position": _rounded(core.get("channel_position")),
        "channel_position_label": _channel_position_label(core.get("channel_position")),
    }


def _trend_overlay(
    rows: list[dict[str, Any]],
    channel_multiplier: float,
) -> dict[str, Any]:
    if len(rows) < 2:
        return {
            "regression_points": [],
            "upper_channel_points": [],
            "lower_channel_points": [],
            "trend_start_date": str(rows[0]["trade_date"]) if rows else None,
            "trend_end_date": str(rows[-1]["trade_date"]) if rows else None,
            "current_point": None,
        }
    values = [_number(row["close_price"]) for row in rows]
    core = calculate_regression_channel(values, channel_multiplier)
    residual = float(core["residual_stddev"]) * channel_multiplier
    centers = [
        {
            "date": str(row["trade_date"]),
            "value": _rounded(float(core["intercept"]) + float(core["slope"]) * index, 4),
        }
        for index, row in enumerate(rows)
    ]
    return {
        "regression_points": centers,
        "upper_channel_points": [
            {"date": point["date"], "value": _rounded(float(point["value"]) + residual, 4)}
            for point in centers
        ],
        "lower_channel_points": [
            {"date": point["date"], "value": _rounded(float(point["value"]) - residual, 4)}
            for point in centers
        ],
        "trend_start_date": str(rows[0]["trade_date"]),
        "trend_end_date": str(rows[-1]["trade_date"]),
        "current_point": {
            "date": str(rows[-1]["trade_date"]),
            "value": _number(rows[-1]["close_price"]),
        },
    }


def _chart_candles(
    all_rows: list[dict[str, Any]],
    display_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    display_dates = {str(row["trade_date"]) for row in display_rows}
    closes: list[float] = []
    result: list[dict[str, Any]] = []
    for row in all_rows:
        closes.append(_number(row["close_price"]))
        date = str(row["trade_date"])
        if date not in display_dates:
            continue
        moving = {
            f"ma{window}": (
                _rounded(fmean(closes[-window:]), 4)
                if len(closes) >= window
                else None
            )
            for window in (5, 10, 20, 60, 120)
        }
        result.append({
            "trade_date": date,
            "open": _number(row.get("open_price")),
            "high": _number(row.get("high_price")),
            "low": _number(row.get("low_price")),
            "close": _number(row.get("close_price")),
            "volume": _number(row.get("volume")),
            "moving_averages": moving,
        })
    return result


def _period_analysis(
    all_rows: list[dict[str, Any]],
    as_of_date: str,
    period: str,
    config: dict[str, Any],
    *,
    include_detail: bool,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    profile = PERIOD_PROFILES[period]
    display_rows = _period_rows(all_rows, as_of_date, period)
    minimum = int(profile["minimum_observations"])
    overall = _period_direction(display_rows, config, minimum)
    timeline = calculate_trend_state_series(
        display_rows,
        configuration=config,
        profile=profile,
    )
    current = timeline["current"] or {
        "direction": "INSUFFICIENT",
        "transition_state": "INSUFFICIENT",
        "trend_start_date": None,
        "persistence_count": 0,
        "trend_strength": None,
        "r_squared": None,
        "channel_position": None,
    }
    if len(display_rows) < minimum:
        current = {
            **current,
            "direction": "INSUFFICIENT",
            "transition_state": "INSUFFICIENT",
            "trend_start_date": None,
            "persistence_count": 0,
        }
    summary = {
        "period": period,
        "display_start_date": str(display_rows[0]["trade_date"]) if display_rows else None,
        "display_end_date": str(display_rows[-1]["trade_date"]) if display_rows else None,
        "observation_count": len(display_rows),
        "minimum_observation_count": minimum,
        "available": len(display_rows) >= minimum,
        "period_direction": overall["direction"],
        "period_direction_label": overall["direction_label"],
        "period_slope": overall["slope"],
        "period_normalized_slope": overall["normalized_slope"],
        "period_r_squared": overall["r_squared"],
        "period_trend_strength": overall["trend_strength"],
        "period_channel_position": overall["channel_position"],
        "period_channel_position_label": overall["channel_position_label"],
        "current_trend_direction": current["direction"],
        "current_trend_label": TREND_LABELS.get(current["direction"], "데이터 부족"),
        "current_state": current["transition_state"],
        "current_state_label": STATE_LABELS.get(current["transition_state"], "데이터 부족"),
        "trend_start_date": current.get("trend_start_date"),
        "persistence_count": current.get("persistence_count", 0),
        "trend_strength": current.get("trend_strength"),
        "r_squared": current.get("r_squared"),
        "channel_position": current.get("channel_position"),
        "channel_position_label": _channel_position_label(current.get("channel_position")),
        "model_label": profile["model_label"],
        "sensitivity_label": profile["sensitivity_label"],
    }
    if not include_detail:
        return summary, None

    existing = calculate_technical_analysis(
        display_rows,
        as_of_date=as_of_date,
        display_period="ALL",
        configuration={**config, "trend_window": int(profile["current_window"])},
    )
    period_text = {
        "1M": "최근 1개월",
        "3M": "최근 3개월",
        "6M": "최근 6개월",
        "1Y": "최근 1년",
        "ALL": "전체 훈련 기간",
    }[period]
    if summary["available"]:
        explanation = (
            f"{period_text} 전체로는 {summary['period_direction_label']} 방향이며, "
            f"{summary['trend_start_date'] or '판정 보류'}부터 "
            f"{summary['current_trend_label']}가 {summary['current_state_label']} 상태입니다. "
            f"현재가는 추세 채널의 {summary['channel_position_label']}에 있습니다."
        )
    else:
        explanation = (
            f"{period_text} 분석에는 최소 {minimum}개 봉이 필요하지만 "
            f"현재 {len(display_rows)}개 봉만 확인됩니다."
        )
    detail = {
        **existing,
        "period_summary": summary,
        "period_direction": overall,
        "current_trend": {
            **current,
            "direction_label": TREND_LABELS.get(current["direction"], "데이터 부족"),
            "state_label": STATE_LABELS.get(current["transition_state"], "데이터 부족"),
            "channel_position_label": _channel_position_label(current.get("channel_position")),
        },
        "period_overlay": _trend_overlay(
            display_rows,
            float(config["channel_multiplier"]),
        ),
        "chart_candles": _chart_candles(display_rows, display_rows),
        "easy_explanation": explanation,
        "next_checks": [
            "기간 추세 채널 하단 또는 상단 유지 여부",
            "MA20 회복 또는 유지 여부",
            "최근 확정 전저점 지지 여부",
        ],
    }
    return summary, detail


def _alignment(period_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    by_period = {item["period"]: item for item in period_summaries}
    short = by_period["1M"]["current_trend_direction"]
    medium = by_period["6M"]["current_trend_direction"]
    long_direction = by_period["1Y"]["period_direction"]
    if short == medium and short in {"UP_TREND", "DOWN_TREND"}:
        alignment_label = (
            "단기·중기 상승 일치"
            if short == "UP_TREND"
            else "단기·중기 하락 일치"
        )
    else:
        alignment_label = "기간별 방향 혼재"
    explanation = (
        f"단기는 {TREND_LABELS.get(short, '데이터 부족')}, "
        f"중기는 {TREND_LABELS.get(medium, '데이터 부족')}이며 "
        f"1년 전체 가격 구조는 {DIRECTION_LABELS.get(long_direction, '데이터 부족')} 방향입니다."
    )
    return {
        "short_direction": short,
        "short_label": TREND_LABELS.get(short, "데이터 부족"),
        "medium_direction": medium,
        "medium_label": TREND_LABELS.get(medium, "데이터 부족"),
        "long_direction": long_direction,
        "long_label": DIRECTION_LABELS.get(long_direction, "데이터 부족"),
        "alignment_label": alignment_label,
        "easy_explanation": explanation,
    }


def calculate_multi_period_analysis(
    rows: list[dict[str, Any]],
    *,
    as_of_date: str,
    selected_period: str = "6M",
    configuration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    selected = selected_period.upper()
    if selected not in TECHNICAL_PERIODS:
        raise ValueError("unsupported selected period")
    config = normalize_configuration(configuration)
    cleaned = _clean_rows(rows, as_of_date)

    detail_started = perf_counter()
    _, selected_detail = _period_analysis(
        cleaned,
        as_of_date,
        selected,
        config,
        include_detail=True,
    )
    selected_detail_ms = (perf_counter() - detail_started) * 1000
    return {
        "as_of_date": as_of_date,
        "default_period": "6M",
        "selected_period": selected,
        "applied_configuration": config,
        "selected_period_detail": selected_detail or {},
        "_calculation_performance": {
            "common_indicator_ms": 0.0,
            "period_summary_ms": round(selected_detail_ms, 3),
            "trend_start_detection_ms": round(selected_detail_ms, 3),
            "selected_period_detail_ms": round(selected_detail_ms, 3),
        },
    }
