from __future__ import annotations

import time
from typing import Any, Literal

import numpy as np

from backend.app.services.drct_pattern_feature_service import (
    CORE_FEATURE_NAMES,
    ENRICHED_FEATURE_NAMES,
    FEATURE_SCHEMA_VERSION,
)
from backend.app.services.marker_training_case_service import MarkerDatasetBuild


FeatureProfile = Literal["CORE", "ENRICHED"]

MARKER_PATTERN_SIGNATURE_VERSION = 1
PATTERN_SIMILARITY_ALGORITHM_VERSION = 1
ROBUST_SCALE_EPSILON = 1e-9
MAD_NORMALIZATION_FACTOR = 1.4826
DISTANCE_CAP = 3.0

FEATURE_METADATA: dict[str, tuple[str, str, str]] = {
    "price_return_5": ("5일 수익률", "가격", "%"),
    "price_return_10": ("10일 수익률", "가격", "%"),
    "price_return_20": ("20일 수익률", "가격", "%"),
    "price_return_60": ("60일 수익률", "가격", "%"),
    "drawdown_from_high_20": ("20일 고점 대비 낙폭", "가격", "%"),
    "drawdown_from_high_60": ("60일 고점 대비 낙폭", "가격", "%"),
    "position_in_range_20": ("20일 가격 범위 위치", "가격", "%"),
    "position_in_range_60": ("60일 가격 범위 위치", "가격", "%"),
    "price_slope_20": ("20일 가격 기울기", "가격", ""),
    "price_slope_60": ("60일 가격 기울기", "가격", ""),
    "ma5_gap_pct": ("5일선 이격도", "이동평균", "%"),
    "ma10_gap_pct": ("10일선 이격도", "이동평균", "%"),
    "ma20_gap_pct": ("20일선 이격도", "이동평균", "%"),
    "ma60_gap_pct": ("60일선 이격도", "이동평균", "%"),
    "volume_vs_ma20": ("당일/20일 평균 거래량", "거래량", "배"),
    "volume_5_20_ratio": ("5일/20일 거래량 비율", "거래량", "배"),
    "rsi14": ("RSI 14", "기술지표", ""),
    "macd_histogram_pct": ("MACD Histogram 비율", "기술지표", "%"),
    "bb_width": ("볼린저밴드 폭", "기술지표", ""),
    "atr14_ratio_to_close": ("ATR 14 비율", "기술지표", "%"),
}


class MarkerPatternSignatureService:
    """Runtime-only robust marker signatures and leave-one-out similarity."""

    @staticmethod
    def feature_names(profile: FeatureProfile) -> tuple[str, ...]:
        return ENRICHED_FEATURE_NAMES if profile == "ENRICHED" else CORE_FEATURE_NAMES

    @staticmethod
    def _eligible(cases: list[dict[str, Any]], profile: FeatureProfile) -> list[dict[str, Any]]:
        status_key = "enriched_status" if profile == "ENRICHED" else "core_status"
        feature_key = "enriched_features" if profile == "ENRICHED" else "core_features"
        return [
            case for case in cases
            if case.get("review_result") == "S"
            and case.get("learning_decision") != "EXCLUDE"
            and case.get(status_key) == "READY"
            and case.get(feature_key) is not None
        ]

    @staticmethod
    def learning_status(case_count: int) -> str:
        if case_count < 3:
            return "INSUFFICIENT"
        if case_count < 5:
            return "EXPERIMENTAL"
        return "TESTABLE"

    @staticmethod
    def _percentile(values: np.ndarray, percentile: float) -> float:
        return float(np.percentile(values, percentile, method="linear"))

    @staticmethod
    def robust_scale(iqr: float, mad: float) -> tuple[float | None, str, str]:
        if iqr > ROBUST_SCALE_EPSILON:
            return iqr, "IQR", "ACTIVE"
        if mad > ROBUST_SCALE_EPSILON:
            return MAD_NORMALIZATION_FACTOR * mad, "MAD", "ACTIVE"
        return None, "NONE", "CONSTANT"

    @classmethod
    def build_signature(cls, cases: list[dict[str, Any]], profile: FeatureProfile) -> dict[str, Any]:
        names = cls.feature_names(profile)
        feature_key = "enriched_features" if profile == "ENRICHED" else "core_features"
        eligible = cls._eligible(cases, profile)
        features: list[dict[str, Any]] = []
        if eligible:
            matrix = np.asarray([[float(case[feature_key][name]) for name in names] for case in eligible], dtype=float)
            for index, name in enumerate(names):
                values = matrix[:, index]
                median = float(np.median(values))
                q1 = cls._percentile(values, 25)
                q3 = cls._percentile(values, 75)
                iqr = q3 - q1
                mad = float(np.median(np.abs(values - median)))
                robust_scale, scale_method, status = cls.robust_scale(iqr, mad)
                label, category, unit = FEATURE_METADATA.get(name, (name, "기타", ""))
                features.append({
                    "key": name, "label": label, "category": category, "unit": unit,
                    "median": median, "q1": q1, "q3": q3, "iqr": iqr, "mad": mad,
                    "min": float(np.min(values)), "max": float(np.max(values)),
                    "valid_count": int(values.size), "robust_scale": robust_scale,
                    "scale_method": scale_method, "status": status,
                })
        return {
            "feature_profile": profile,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "pattern_signature_version": MARKER_PATTERN_SIGNATURE_VERSION,
            "similarity_algorithm_version": PATTERN_SIMILARITY_ALGORITHM_VERSION,
            "case_count": len(eligible), "status": cls.learning_status(len(eligible)),
            "active_feature_count": sum(item["status"] == "ACTIVE" for item in features),
            "constant_feature_count": sum(item["status"] == "CONSTANT" for item in features),
            "features": features,
        }

    @staticmethod
    def score(features: dict[str, float], signature: dict[str, Any]) -> dict[str, Any] | None:
        distances = []
        details = []
        for feature in signature["features"]:
            if feature["status"] != "ACTIVE" or feature["key"] not in features:
                continue
            raw_distance = abs(float(features[feature["key"]]) - float(feature["median"])) / float(feature["robust_scale"])
            distance = min(raw_distance, DISTANCE_CAP)
            distances.append(distance)
            details.append({
                "key": feature["key"], "label": feature["label"], "unit": feature["unit"],
                "case_value": float(features[feature["key"]]), "signature_median": float(feature["median"]),
                "robust_distance": float(distance), "raw_robust_distance": float(raw_distance),
            })
        if not distances:
            return None
        pattern_distance = float(np.median(np.asarray(distances, dtype=float)))
        return {
            "pattern_distance": pattern_distance,
            "pattern_similarity": 100.0 / (1.0 + pattern_distance),
            "usable_feature_count": len(distances),
            "excluded_constant_feature_count": int(signature["constant_feature_count"]),
            "feature_distances": sorted(details, key=lambda item: (-item["robust_distance"], item["key"])),
        }

    @classmethod
    def validate(cls, cases: list[dict[str, Any]], profile: FeatureProfile) -> dict[str, Any]:
        eligible = cls._eligible(cases, profile)
        status = cls.learning_status(len(eligible))
        if len(eligible) < 3:
            return {"feature_profile": profile, "status": status, "evaluated_count": 0, "distribution": None, "cases": []}
        feature_key = "enriched_features" if profile == "ENRICHED" else "core_features"
        rows = []
        for index, case in enumerate(eligible):
            training_cases = eligible[:index] + eligible[index + 1:]
            signature = cls.build_signature(training_cases, profile)
            score = cls.score(case[feature_key], signature)
            if score is None:
                continue
            rows.append({
                "chart_marker_event_id": int(case["chart_marker_event_id"]),
                "stock_id": int(case["stock_id"]), "stock_code": str(case["stock_code"]),
                "stock_name": str(case["stock_name"]), "d0": str(case["d0"]),
                "review_result": case.get("review_result"), "feature_profile": profile,
                "pattern_distance": score["pattern_distance"], "pattern_similarity": score["pattern_similarity"],
                "usable_feature_count": score["usable_feature_count"],
                "excluded_constant_feature_count": score["excluded_constant_feature_count"],
            })
        values = np.asarray([row["pattern_similarity"] for row in rows], dtype=float)
        distribution = None if not rows else {
            "min": float(np.min(values)), "p10": cls._percentile(values, 10),
            "p25": cls._percentile(values, 25), "median": float(np.median(values)),
            "p75": cls._percentile(values, 75), "p90": cls._percentile(values, 90),
            "max": float(np.max(values)),
            "iqr": cls._percentile(values, 75) - cls._percentile(values, 25),
        }
        return {"feature_profile": profile, "status": status, "evaluated_count": len(rows),
                "distribution": distribution, "cases": sorted(rows, key=lambda row: (row["pattern_similarity"], row["d0"], row["chart_marker_event_id"]))}

    @classmethod
    def signature_response(cls, build: MarkerDatasetBuild, profile: FeatureProfile) -> dict[str, Any]:
        started = time.perf_counter()
        result = cls.build_signature(build.cases, profile)
        return {"marker": build.marker, **result, "elapsed_ms": int((time.perf_counter() - started) * 1000),
                "dataset_elapsed_ms": build.elapsed_ms, "storage_policy": "RUNTIME_ONLY"}

    @classmethod
    def validation_response(cls, build: MarkerDatasetBuild, profile: FeatureProfile) -> dict[str, Any]:
        started = time.perf_counter()
        result = cls.validate(build.cases, profile)
        return {"marker": build.marker, "feature_schema_version": FEATURE_SCHEMA_VERSION,
                "pattern_signature_version": MARKER_PATTERN_SIGNATURE_VERSION,
                "similarity_algorithm_version": PATTERN_SIMILARITY_ALGORITHM_VERSION,
                **result, "elapsed_ms": int((time.perf_counter() - started) * 1000),
                "dataset_elapsed_ms": build.elapsed_ms, "storage_policy": "RUNTIME_ONLY"}

    @classmethod
    def case_detail(cls, build: MarkerDatasetBuild, event_id: int, profile: FeatureProfile) -> dict[str, Any] | None:
        eligible = cls._eligible(build.cases, profile)
        selected = next((case for case in eligible if int(case["chart_marker_event_id"]) == event_id), None)
        if selected is None or len(eligible) < 3:
            return None
        training_cases = [case for case in eligible if int(case["chart_marker_event_id"]) != event_id]
        signature = cls.build_signature(training_cases, profile)
        feature_key = "enriched_features" if profile == "ENRICHED" else "core_features"
        score = cls.score(selected[feature_key], signature)
        if score is None:
            return None
        return {
            "chart_marker_event_id": event_id, "marker": build.marker, "stock_id": int(selected["stock_id"]),
            "stock_code": str(selected["stock_code"]), "stock_name": str(selected["stock_name"]),
            "d0": str(selected["d0"]), "review_result": selected.get("review_result"),
            "feature_profile": profile, "pattern_distance": score["pattern_distance"],
            "pattern_similarity": score["pattern_similarity"],
            "usable_feature_count": score["usable_feature_count"],
            "excluded_constant_feature_count": score["excluded_constant_feature_count"],
            "top_feature_differences": score["feature_distances"][:5], "storage_policy": "RUNTIME_ONLY",
        }
