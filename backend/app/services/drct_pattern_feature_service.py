from __future__ import annotations

from typing import Any

import numpy as np


FEATURE_SCHEMA_VERSION = 1
CORE_FEATURE_NAMES = (
    "price_return_5", "price_return_10", "price_return_20", "price_return_60",
    "drawdown_from_high_20", "drawdown_from_high_60",
    "position_in_range_20", "position_in_range_60",
    "price_slope_20", "price_slope_60",
    "ma5_gap_pct", "ma10_gap_pct", "ma20_gap_pct", "ma60_gap_pct",
    "volume_vs_ma20", "volume_5_20_ratio",
)
ENRICHED_EXTRA_FEATURE_NAMES = (
    "rsi14", "macd_histogram_pct", "bb_width", "atr14_ratio_to_close",
)
ENRICHED_FEATURE_NAMES = CORE_FEATURE_NAMES + ENRICHED_EXTRA_FEATURE_NAMES


class PatternFeatureService:
    @staticmethod
    def _number(value: Any) -> float | None:
        if value is None:
            return None
        number = float(value)
        return number if np.isfinite(number) else None

    @staticmethod
    def _normalized_slope(rows: list[dict[str, Any]], length: int, d0_close: float) -> float | None:
        if len(rows) < length or d0_close == 0:
            return None
        chronological = [float(row["close_price"]) / d0_close * 100 for row in reversed(rows[:length]) if row.get("close_price") is not None]
        if len(chronological) != length:
            return None
        x = np.arange(length, dtype=float)
        return float(np.polyfit(x, np.asarray(chronological, dtype=float), 1)[0])

    @classmethod
    def core(cls, rows_desc: list[dict[str, Any]]) -> tuple[str, dict[str, float] | None, list[str]]:
        missing: list[str] = []
        if len(rows_desc) < 61 or rows_desc[0].get("close_price") is None:
            return "CORE_DATA_INCOMPLETE", None, ["D0 포함 61거래봉이 필요합니다."]
        close = float(rows_desc[0]["close_price"])
        if close == 0:
            return "CORE_DATA_INCOMPLETE", None, ["D0 종가가 0입니다."]
        features: dict[str, float | None] = {}
        for period in (5, 10, 20, 60):
            prior = cls._number(rows_desc[period].get("close_price"))
            features[f"price_return_{period}"] = None if prior in (None, 0) else (close / prior - 1) * 100
        for period in (20, 60):
            window = rows_desc[:period]
            highs = [cls._number(row.get("high_price")) for row in window]
            lows = [cls._number(row.get("low_price")) for row in window]
            if any(value is None for value in highs + lows):
                features[f"drawdown_from_high_{period}"] = None
                features[f"position_in_range_{period}"] = None
            else:
                high, low = max(highs), min(lows)
                features[f"drawdown_from_high_{period}"] = None if high == 0 else (close / high - 1) * 100
                features[f"position_in_range_{period}"] = None if high == low else (close - low) / (high - low) * 100
            features[f"price_slope_{period}"] = cls._normalized_slope(rows_desc, period, close)
        for period in (5, 10, 20, 60):
            ma = cls._number(rows_desc[0].get(f"ma{period}"))
            features[f"ma{period}_gap_pct"] = None if ma in (None, 0) else (close / ma - 1) * 100
        volumes = [cls._number(row.get("volume")) for row in rows_desc[:20]]
        if any(value is None for value in volumes) or sum(volumes) == 0:
            features["volume_vs_ma20"] = None
            features["volume_5_20_ratio"] = None
        else:
            volume_ma20 = sum(volumes) / 20
            volume_ma5 = sum(volumes[:5]) / 5
            features["volume_vs_ma20"] = volumes[0] / volume_ma20
            features["volume_5_20_ratio"] = volume_ma5 / volume_ma20
        for name, value in features.items():
            if value is None or not np.isfinite(float(value)):
                missing.append(name)
        if missing:
            return "CORE_DATA_INCOMPLETE", None, missing
        return "READY", {name: float(features[name]) for name in CORE_FEATURE_NAMES}, []

    @classmethod
    def enriched(cls, core_features: dict[str, float] | None, indicator: dict[str, Any] | None, d0_close: float | None) -> tuple[str, dict[str, float] | None, list[str]]:
        if core_features is None:
            return "ENRICHED_DATA_INCOMPLETE", None, ["CORE Feature가 준비되지 않았습니다."]
        if indicator is None:
            return "ENRICHED_DATA_INCOMPLETE", None, ["D0 기술지표가 없습니다."]
        if d0_close in (None, 0):
            return "ENRICHED_DATA_INCOMPLETE", None, ["MACD 정규화에 필요한 D0 종가가 없습니다."]
        values = {
            "rsi14": cls._number(indicator.get("rsi14")),
            "macd_histogram_pct": None if indicator.get("macd_histogram") is None else float(indicator["macd_histogram"]) / float(d0_close) * 100,
            "bb_width": cls._number(indicator.get("bb_width")),
            "atr14_ratio_to_close": cls._number(indicator.get("atr14_ratio_to_close")),
        }
        missing = [name for name, value in values.items() if value is None or not np.isfinite(float(value))]
        if missing:
            return "ENRICHED_DATA_INCOMPLETE", None, missing
        return "READY", {**core_features, **{name: float(values[name]) for name in ENRICHED_EXTRA_FEATURE_NAMES}}, []
