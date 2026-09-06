from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


BASELINE_POLICY_VERSION = "CANDIDATE_POLICY_BASELINE_V1"
SHADOW_POLICY_VERSION = "CANDIDATE_POLICY_SHADOW_V1"
SHADOW_MARKET_REFERENCE_LEVEL = 90

# Candidate range is descriptive UX only. It is not an investment or quality rating.
CANDIDATE_RANGE_RATIO_LIMITS = {
    "NARROW": 5.0,
    "MODERATE": 15.0,
    "BROAD": 35.0,
}


class MarkerCandidatePolicyResearchService:
    """Pure runtime research for friendly range labels and a non-operating shadow gate."""

    @staticmethod
    def _range_status(candidate_ratio: float) -> str:
        if candidate_ratio <= CANDIDATE_RANGE_RATIO_LIMITS["NARROW"]:
            return "NARROW"
        if candidate_ratio <= CANDIDATE_RANGE_RATIO_LIMITS["MODERATE"]:
            return "MODERATE"
        if candidate_ratio <= CANDIDATE_RANGE_RATIO_LIMITS["BROAD"]:
            return "BROAD"
        return "VERY_BROAD"

    @staticmethod
    def _discrimination_status(
        loo_distribution: Mapping[str, float], current_distribution: Mapping[str, float],
    ) -> str:
        median_gap = float(loo_distribution["median"]) - float(current_distribution["median"])
        p75_gap = float(loo_distribution["p75"]) - float(current_distribution["p75"])
        if median_gap <= 0:
            return "REVIEW"
        if median_gap < 5 or p75_gap < 5:
            return "WEAK"
        return "GOOD"

    @staticmethod
    def _sample(row: Mapping[str, Any], baseline_threshold: float) -> dict[str, Any]:
        return {
            "stock_id": int(row["stock_id"]),
            "stock_code": str(row["stock_code"]),
            "stock_name": str(row["stock_name"]),
            "theme_names": list(row["theme_names"]),
            "similarity": float(row["similarity"]),
            "empirical_percentile": float(row["empirical_percentile"]),
            "is_current_candidate": float(row["similarity"]) >= baseline_threshold,
        }

    @classmethod
    def evaluate(
        cls,
        *,
        loo_distribution: Mapping[str, float],
        current_distribution: Mapping[str, float],
        current_rows: Sequence[Mapping[str, Any]],
        thresholds: Mapping[str, Mapping[str, Any]],
    ) -> tuple[dict[str, Any], list[int]]:
        current_count = int(thresholds["p25"]["candidate_count"])
        current_total = len(current_rows)
        current_ratio = current_count / current_total * 100 if current_total else 0.0
        range_status = cls._range_status(current_ratio)
        discrimination_status = cls._discrimination_status(loo_distribution, current_distribution)
        strict_count = int(thresholds["p75"]["candidate_count"])

        if discrimination_status == "REVIEW":
            interpretation_status = "HARD_TO_DISTINGUISH"
            action_hint = "REVIEW_STRICT_AND_FEATURES"
        elif range_status in ("NARROW", "MODERATE"):
            interpretation_status = "SELECTIVE"
            action_hint = "KEEP_CURRENT_REVIEW"
        elif strict_count <= current_count * 0.5:
            interpretation_status = "BROAD_REDUCES_STRICT"
            action_hint = "REVIEW_STRICT_CHARTS"
        else:
            interpretation_status = "BROAD_STABLE"
            action_hint = "REVIEW_STRICT_AND_FEATURES"

        baseline_threshold = float(loo_distribution["p25"])
        market_threshold = float(current_distribution["p90"])
        shadow_threshold = max(baseline_threshold, market_threshold)
        shadow_rows = [row for row in current_rows if float(row["similarity"]) >= shadow_threshold]
        shadow_stock_ids = [int(row["stock_id"]) for row in shadow_rows]

        reference_levels = {
            f"level_{level}": {
                "level": level,
                "similarity_threshold": float(loo_distribution[key]),
                "candidate_count": int(thresholds[key]["candidate_count"]),
                "candidate_ratio": float(thresholds[key]["candidate_ratio"]),
            }
            for level, key in ((25, "p25"), (50, "median"), (75, "p75"), (90, "p90"))
        }
        result = {
            "current_candidate_count": current_count,
            "candidate_range_status": range_status,
            "discrimination_status": discrimination_status,
            "interpretation_status": interpretation_status,
            "action_hint": action_hint,
            "reference_levels": reference_levels,
            "shadow": {
                "status": "VALIDATING",
                "candidate_count": len(shadow_rows),
                "candidate_ratio": len(shadow_rows) / current_total * 100 if current_total else 0.0,
                "similarity_threshold": shadow_threshold,
                "historical_reference_level": 25,
                "market_reference_level": SHADOW_MARKET_REFERENCE_LEVEL,
                "policy_version": SHADOW_POLICY_VERSION,
                "samples": [cls._sample(row, baseline_threshold) for row in shadow_rows[:10]],
            },
        }
        return result, shadow_stock_ids
