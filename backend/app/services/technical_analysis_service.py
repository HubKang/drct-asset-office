from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import json
import math
from statistics import fmean, pstdev
from threading import Lock
from time import monotonic, perf_counter
from typing import Any

DEFAULT_TECHNICAL_CONFIGURATION = {
    "short_window": 20, "medium_window": 60, "trend_window": 120,
    "channel_multiplier": 1.8, "minimum_break_persistence": 3,
    "reversal_persistence": 5, "swing_confirmation_width": 3,
    "minimum_trend_strength": 1.0, "minimum_r_squared": 0.18,
}
DISPLAY_PERIOD_DAYS = {"1M": 31, "3M": 93, "6M": 186, "1Y": 366}
TECHNICAL_PERIODS = ("1M", "3M", "6M", "1Y", "ALL")
PERIOD_PROFILES: dict[str, dict[str, Any]] = {
    "1M": {"model_label": "단기 추세형", "sensitivity_label": "빠름", "current_window": 12, "minimum_observations": 8, "direction_persistence": 2, "break_persistence": 2},
    "3M": {"model_label": "스윙 추세형", "sensitivity_label": "민감", "current_window": 24, "minimum_observations": 15, "direction_persistence": 3, "break_persistence": 2},
    "6M": {"model_label": "중기 추세형", "sensitivity_label": "보통", "current_window": 40, "minimum_observations": 20, "direction_persistence": 4, "break_persistence": 3},
    "1Y": {"model_label": "장기 맥락형", "sensitivity_label": "완만", "current_window": 60, "minimum_observations": 30, "direction_persistence": 5, "break_persistence": 3},
    "ALL": {"model_label": "전체 맥락형", "sensitivity_label": "완만", "current_window": 80, "minimum_observations": 30, "direction_persistence": 5, "break_persistence": 3},
}


class BoundedTtlCache:
    def __init__(self, max_entries: int = 128, ttl_seconds: int = 300) -> None:
        self.max_entries, self.ttl_seconds = max_entries, ttl_seconds
        self._values: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()
        self._lock = Lock()

    def get(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            item = self._values.pop(key, None)
            if item is None or item[0] <= monotonic():
                return None
            self._values[key] = item
            return deepcopy(item[1])

    def put(self, key: str, value: dict[str, Any]) -> None:
        with self._lock:
            self._values.pop(key, None)
            self._values[key] = (monotonic() + self.ttl_seconds, deepcopy(value))
            while len(self._values) > self.max_entries:
                self._values.popitem(last=False)


TECHNICAL_PREVIEW_CACHE = BoundedTtlCache()
MULTI_PERIOD_PREVIEW_CACHE = BoundedTtlCache(max_entries=160, ttl_seconds=300)


def normalize_configuration(override: dict[str, Any] | None = None) -> dict[str, Any]:
    config = {**DEFAULT_TECHNICAL_CONFIGURATION, **(override or {})}
    limits = {
        "short_window": (2, 120), "medium_window": (5, 240), "trend_window": (20, 240),
        "minimum_break_persistence": (1, 20), "reversal_persistence": (1, 30),
        "swing_confirmation_width": (1, 10),
    }
    for key, (low, high) in limits.items():
        config[key] = max(low, min(high, int(config[key])))
    config["channel_multiplier"] = max(.5, min(5.0, float(config["channel_multiplier"])))
    config["minimum_trend_strength"] = max(0.0, min(20.0, float(config["minimum_trend_strength"])))
    config["minimum_r_squared"] = max(0.0, min(1.0, float(config["minimum_r_squared"])))
    return config


def configuration_hash(config: dict[str, Any]) -> str:
    raw = json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _num(value: Any) -> float:
    try:
        result = float(value)
        return result if math.isfinite(result) else 0.0
    except (TypeError, ValueError):
        return 0.0


def _rnd(value: float | None, digits: int = 4) -> float | None:
    return None if value is None or not math.isfinite(value) else round(value, digits)


def _pct(current: float, reference: float | None) -> float | None:
    return None if reference is None or math.isclose(reference, 0) else _rnd((current-reference)/reference*100, 2)


def _avg(values: list[float]) -> float | None:
    return fmean(values) if values else None


def _ma(values: list[float], window: int, end: int | None = None) -> float | None:
    endpoint = len(values) if end is None else end
    return fmean(values[endpoint-window:endpoint]) if endpoint >= window else None


def _regression(values: list[float]) -> dict[str, float]:
    size, x_mean, y_mean = len(values), (len(values)-1)/2, fmean(values)
    denominator = sum((idx-x_mean)**2 for idx in range(size))
    slope = 0.0 if math.isclose(denominator, 0) else sum((idx-x_mean)*(value-y_mean) for idx, value in enumerate(values))/denominator
    intercept = y_mean-slope*x_mean
    centers = [intercept+slope*idx for idx in range(size)]
    residuals = [value-center for value, center in zip(values, centers)]
    total, residual = sum((v-y_mean)**2 for v in values), sum(v**2 for v in residuals)
    return {"slope": slope, "intercept": intercept, "last_center": centers[-1],
            "r_squared": 0.0 if math.isclose(total, 0) else max(0.0, min(1.0, 1-residual/total)),
            "residual_stddev": pstdev(residuals) if len(residuals) > 1 else 0.0}


def calculate_regression_channel(values: list[float], channel_multiplier: float) -> dict[str, float | None]:
    """Pure shared trend math used by market signals and training previews."""
    regression = _regression(values)
    normalized = regression["slope"] / max(abs(fmean(values)), 1e-9) * len(values) * 100
    strength = abs(normalized) * max(regression["r_squared"], .01)
    upper = regression["last_center"] + channel_multiplier * regression["residual_stddev"]
    lower = regression["last_center"] - channel_multiplier * regression["residual_stddev"]
    width = upper - lower
    return {
        **regression,
        "normalized_slope": normalized,
        "trend_strength": strength,
        "channel_upper": upper,
        "channel_lower": lower,
        "channel_position": None if math.isclose(width, 0) else (values[-1] - lower) / width,
    }


def _atr(rows: list[dict[str, Any]], window: int = 14) -> float | None:
    ranges = []
    for idx, row in enumerate(rows):
        high, low = _num(row.get("high_price")), _num(row.get("low_price"))
        previous = _num(rows[idx-1].get("close_price")) if idx else 0
        ranges.append(max(high-low, abs(high-previous), abs(low-previous)) if previous else high-low)
    return _avg(ranges[-window:]) if len(ranges) >= window else None


def _latest_cross(closes: list[float], dates: list[str]) -> dict[str, Any] | None:
    for end in range(len(closes), 20, -1):
        s0, l0, s1, l1 = _ma(closes, 5, end), _ma(closes, 20, end), _ma(closes, 5, end-1), _ma(closes, 20, end-1)
        if None in (s0, l0, s1, l1):
            continue
        if s1 <= l1 and s0 > l0:
            return {"type": "GOLDEN_CROSS", "label": "MA5가 MA20 위로 교차", "date": dates[end-1]}
        if s1 >= l1 and s0 < l0:
            return {"type": "DEAD_CROSS", "label": "MA5가 MA20 아래로 교차", "date": dates[end-1]}
    return None


def _trend(values: list[float], regression: dict[str, float] | None, config: dict[str, Any]) -> dict[str, Any]:
    if regression is None or len(values) < 20:
        return {"direction": "INSUFFICIENT", "direction_label": "데이터 부족", "state": "INSUFFICIENT", "state_label": "데이터 부족"}
    core = calculate_regression_channel(values, config["channel_multiplier"])
    normalized, strength = float(core["normalized_slope"]), float(core["trend_strength"])
    if regression["r_squared"] < config["minimum_r_squared"] or abs(normalized) < config["minimum_trend_strength"]:
        direction, label = "SIDEWAYS", "횡보"
    elif normalized > 0:
        direction, label = "UP", "상승 추세"
    else:
        direction, label = "DOWN", "하락 추세"
    residual = regression["residual_stddev"]
    upper = float(core["channel_upper"])
    lower = float(core["channel_lower"])
    flags = []
    for idx, value in enumerate(values):
        center = regression["intercept"]+regression["slope"]*idx
        flags.append("UP" if value > center+config["channel_multiplier"]*residual else "DOWN" if value < center-config["channel_multiplier"]*residual else None)
    side, tail = flags[-1], 0
    for flag in reversed(flags):
        if flag != side or flag is None:
            break
        tail += 1
    confirmed = side is not None and tail >= config["minimum_break_persistence"]
    state = "BREAK_CONFIRMED" if confirmed else "BREAK_CANDIDATE" if side else "MAINTAINED"
    duration, upward = 1, normalized >= 0
    for idx in range(len(values)-1, 0, -1):
        if (values[idx] >= values[idx-1]) != upward:
            break
        duration += 1
    width = upper-lower
    return {"direction": direction, "direction_label": label, "state": state,
            "state_label": {"BREAK_CONFIRMED": "추세 이탈 확인", "BREAK_CANDIDATE": "추세 이탈 후보", "MAINTAINED": "추세 유지"}[state],
            "regression_slope": _rnd(regression["slope"], 8), "normalized_slope": _rnd(normalized, 6),
            "r_squared": _rnd(regression["r_squared"], 6), "trend_strength": _rnd(strength, 6),
            "channel_position": None if math.isclose(width, 0) else _rnd((values[-1]-lower)/width, 6),
            "duration_count": duration, "break_candidate": side is not None, "break_confirmed": confirmed,
            "false_break": bool(side is None and any(flag is not None for flag in flags[-6:-1])),
            "reversal_confirmed": False, "channel_center": _rnd(regression["last_center"]),
            "channel_upper": _rnd(upper), "channel_lower": _rnd(lower)}


def _moving(closes: list[float], dates: list[str], current: float) -> dict[str, Any]:
    result, available = {}, []
    for window in (5, 10, 20, 60, 120):
        value, previous = _ma(closes, window), _ma(closes, window, len(closes)-1)
        result[f"ma{window}"] = {"value": _rnd(value), "distance_pct": _pct(current, value),
                                  "slope_pct": _pct(value or 0, previous) if value is not None and previous is not None else None}
        if value is not None:
            available.append(value)
    if len(available) < 3:
        arrangement, label = "INSUFFICIENT", "데이터 부족"
    elif all(a > b for a, b in zip(available, available[1:])):
        arrangement, label = "BULLISH", "정배열"
    elif all(a < b for a, b in zip(available, available[1:])):
        arrangement, label = "BEARISH", "역배열"
    else:
        arrangement, label = "MIXED", "혼조"
    return {"values": result, "arrangement": arrangement, "arrangement_label": label, "latest_cross": _latest_cross(closes, dates)}


def _volume(rows: list[dict[str, Any]]) -> dict[str, Any]:
    volumes = [_num(row.get("volume")) for row in rows]
    current, avg5, avg20 = volumes[-1], _avg(volumes[-5:]), _avg(volumes[-20:])
    ratio = current/avg20 if avg20 else None
    price_up = len(rows) < 2 or _num(rows[-1]["close_price"]) >= _num(rows[-2]["close_price"])
    observation = ("가격 상승과 거래량 증가가 함께 나타났습니다." if price_up and ratio is not None and ratio >= 1
                   else "가격 하락과 거래량 증가가 함께 나타났습니다." if not price_up and ratio is not None and ratio >= 1
                   else "가격은 상승했지만 거래량은 평균보다 낮습니다." if price_up
                   else "가격 하락 중 거래량은 평균보다 낮습니다.")
    up = [volumes[idx] for idx in range(1, len(rows)) if _num(rows[idx]["close_price"]) >= _num(rows[idx-1]["close_price"])]
    down = [volumes[idx] for idx in range(1, len(rows)) if _num(rows[idx]["close_price"]) < _num(rows[idx-1]["close_price"])]
    spike = next(({"date": str(rows[idx]["trade_date"]), "volume": volumes[idx]} for idx in range(len(rows)-1, 19, -1)
                  if (_avg20 := _avg(volumes[idx-20:idx])) and volumes[idx] >= _avg20*1.8), None)
    return {"current": _rnd(current, 0), "average_5": _rnd(avg5, 0), "average_20": _rnd(avg20, 0),
            "ratio_to_average_20": _rnd(ratio, 2), "latest_spike": spike,
            "up_candle_average": _rnd(_avg(up), 0), "down_candle_average": _rnd(_avg(down), 0), "observation": observation}


def _swings(rows: list[dict[str, Any]], width: int, current: float) -> dict[str, Any]:
    highs, lows = [], []
    for idx in range(width, len(rows)-width):
        segment = rows[idx-width:idx+width+1]
        high, low = _num(rows[idx].get("high_price")), _num(rows[idx].get("low_price"))
        if high >= max(_num(row.get("high_price")) for row in segment):
            highs.append({"date": str(rows[idx]["trade_date"]), "value": high, "status": "CONFIRMED"})
        if low <= min(_num(row.get("low_price")) for row in segment):
            lows.append({"date": str(rows[idx]["trade_date"]), "value": low, "status": "CONFIRMED"})
    recent = rows[max(0, len(rows)-width-1):]
    high_candidate = max(recent, key=lambda row: _num(row.get("high_price"))) if recent else None
    low_candidate = min(recent, key=lambda row: _num(row.get("low_price"))) if recent else None
    result = {"confirmed_high": highs[-1] if highs else None, "confirmed_low": lows[-1] if lows else None,
              "high_candidate": {"date": str(high_candidate["trade_date"]), "value": _num(high_candidate.get("high_price")), "status": "CANDIDATE"} if high_candidate else None,
              "low_candidate": {"date": str(low_candidate["trade_date"]), "value": _num(low_candidate.get("low_price")), "status": "CANDIDATE"} if low_candidate else None}
    for value in result.values():
        if value:
            value["distance_pct"] = _pct(current, value["value"])
    return result


def _price_range(rows: list[dict[str, Any]], window: int, current: float) -> dict[str, Any]:
    sample = rows[-window:]
    high, low = max((_num(row.get("high_price")) for row in sample), default=0), min((_num(row.get("low_price")) for row in sample), default=0)
    return {"high": high or None, "low": low or None, "high_distance_pct": _pct(current, high), "low_distance_pct": _pct(current, low)}


def _candle(rows: list[dict[str, Any]]) -> dict[str, Any]:
    row = rows[-1]
    open_price, high, low, close = (_num(row.get(key)) for key in ("open_price", "high_price", "low_price", "close_price"))
    previous = _num(rows[-2].get("close_price")) if len(rows) > 1 else 0
    full_range, body, atr = max(high-low, 0), abs(close-open_price), _atr(rows)
    upper, lower = max(0, high-max(open_price, close)), max(0, min(open_price, close)-low)
    return {"date": str(row["trade_date"]), "open": open_price, "high": high, "low": low, "close": close,
            "change_pct": _pct(close, previous), "intraday_range_pct": _pct(high, low),
            "direction": "BULLISH" if close >= open_price else "BEARISH", "direction_label": "양봉" if close >= open_price else "음봉",
            "body_ratio": _rnd(body/full_range, 2) if full_range else None,
            "upper_wick_ratio": _rnd(upper/full_range, 2) if full_range else None,
            "lower_wick_ratio": _rnd(lower/full_range, 2) if full_range else None,
            "gap": "UP" if previous and low > previous else "DOWN" if previous and high < previous else "NONE",
            "range_to_atr": _rnd(full_range/atr, 2) if atr else None,
            "observation": "장중 저가에서 일부 회복했지만 종가는 시가 아래에서 마감했습니다." if close < open_price and lower > body*.5 else "현재 캔들의 가격 범위와 꼬리 비율을 함께 확인하세요."}


def _overlay(rows: list[dict[str, Any]], regression: dict[str, float] | None, config: dict[str, Any], current: float) -> dict[str, Any]:
    if not regression:
        return {"regression_points": [], "upper_channel_points": [], "lower_channel_points": [], "analysis_start_date": str(rows[0]["trade_date"]) if rows else None, "current_point": None}
    residual = regression["residual_stddev"]*config["channel_multiplier"]
    centers = [{"date": str(row["trade_date"]), "value": _rnd(regression["intercept"]+regression["slope"]*idx)} for idx, row in enumerate(rows)]
    return {"regression_points": centers,
            "upper_channel_points": [{"date": p["date"], "value": _rnd(float(p["value"])+residual)} for p in centers],
            "lower_channel_points": [{"date": p["date"], "value": _rnd(float(p["value"])-residual)} for p in centers],
            "analysis_start_date": str(rows[0]["trade_date"]), "current_point": {"date": str(rows[-1]["trade_date"]), "value": current}}


def _summary(trend: dict[str, Any], moving: dict[str, Any], volume: dict[str, Any], position: dict[str, Any], candle: dict[str, Any], volatility: dict[str, Any]) -> dict[str, Any]:
    direction, state, ratio = trend.get("direction_label", "데이터 부족"), trend.get("state_label", "데이터 부족"), volume.get("ratio_to_average_20")
    compact = [moving.get("arrangement_label", "데이터 부족")]
    if ratio is not None:
        compact.append(f"거래량 20일 평균의 {ratio:.2f}배")
    high_distance = (position.get("confirmed_high") or {}).get("distance_pct")
    if high_distance is not None:
        compact.append(f"전고점 대비 {high_distance:+.1f}%")
    checks = (["최근 전저점 지지 여부"] if position.get("confirmed_low") else []) + (["거래량 증가 동반 여부"] if ratio is None or ratio < 1 else []) + ["MA20 회복 또는 유지 여부"]
    return {"status_label": f"{direction} · {state}", "compact_items": compact[:3],
            "easy_explanation": f"{direction} 상태이며 현재 판정은 {state}입니다. {volume.get('observation', '')}".strip(),
            "next_checks": checks[:3], "current_candle_label": candle.get("direction_label"),
            "volatility_label": f"ATR {volatility['atr_pct']:.2f}%" if volatility.get("atr_pct") is not None else "ATR 데이터 부족"}


def calculate_technical_analysis(rows: list[dict[str, Any]], *, as_of_date: str, display_period: str, configuration: dict[str, Any] | None = None) -> dict[str, Any]:
    config, period = normalize_configuration(configuration), display_period.upper()
    if period not in {*DISPLAY_PERIOD_DAYS, "ALL"}:
        raise ValueError("unsupported display period")
    rows = sorted((dict(row) for row in rows if str(row.get("trade_date") or "") <= as_of_date and _num(row.get("close_price")) > 0), key=lambda row: str(row["trade_date"]))
    if not rows:
        return _empty(as_of_date, period, config)
    dates, closes = [str(row["trade_date"]) for row in rows], [_num(row["close_price"]) for row in rows]
    current = closes[-1]
    cutoff = None if period == "ALL" else (datetime.strptime(as_of_date, "%Y-%m-%d").date()-timedelta(days=DISPLAY_PERIOD_DAYS[period])).isoformat()
    display = rows if cutoff is None else [row for row in rows if str(row["trade_date"]) >= cutoff]
    analysis = rows[-min(config["trend_window"], len(rows)):]
    values, regression = closes[-len(analysis):], None
    if len(analysis) >= 2:
        regression = _regression(values)
    trend, moving, volume = _trend(values, regression, config), _moving(closes, dates, current), _volume(rows)
    position = {**_swings(rows, config["swing_confirmation_width"], current), **{f"range_{window}": _price_range(rows, window, current) for window in (20, 60, 120)}}
    candle, atr = _candle(rows), _atr(rows)
    volatility = {"atr_14": _rnd(atr), "atr_pct": _pct(current+(atr or 0), current) if atr else None}
    return {"as_of_date": as_of_date, "display_period": period,
            "display_start_date": str(display[0]["trade_date"]), "display_end_date": str(display[-1]["trade_date"]), "display_observation_count": len(display),
            "analysis_start_date": str(analysis[0]["trade_date"]), "analysis_end_date": str(analysis[-1]["trade_date"]), "analysis_observation_count": len(analysis),
            "applied_configuration": config, "trend": trend, "moving_averages": moving, "volume": volume, "price_position": position,
            "current_candle": candle, "volatility": volatility, "summary": _summary(trend, moving, volume, position, candle, volatility),
            "overlay": _overlay(analysis, regression, config, current)}


def _empty(as_of_date: str, period: str, config: dict[str, Any]) -> dict[str, Any]:
    return {"as_of_date": as_of_date, "display_period": period, "display_start_date": None, "display_end_date": None,
            "display_observation_count": 0, "analysis_start_date": None, "analysis_end_date": None, "analysis_observation_count": 0,
            "applied_configuration": config,
            "trend": {"direction": "INSUFFICIENT", "direction_label": "데이터 부족", "state": "INSUFFICIENT", "state_label": "데이터 부족"},
            "moving_averages": {"values": {}, "arrangement": "INSUFFICIENT", "arrangement_label": "데이터 부족", "latest_cross": None},
            "volume": {}, "price_position": {}, "current_candle": {}, "volatility": {},
            "summary": {"status_label": "데이터 부족", "compact_items": [], "easy_explanation": "분석할 가격 데이터가 부족합니다.", "next_checks": []},
            "overlay": {"regression_points": [], "upper_channel_points": [], "lower_channel_points": [], "analysis_start_date": None, "current_point": None}}
