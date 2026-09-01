from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.services.drct_pattern_baseline_service import (
    LOGISTIC_MIN_FAILURE,
    LOGISTIC_MIN_SUCCESS,
    LOGISTIC_MIN_TOTAL,
    PROTOTYPE_MIN_SUCCESS,
    PatternBaselineService,
)
from backend.app.services.drct_pattern_feature_service import CORE_FEATURE_NAMES, ENRICHED_FEATURE_NAMES, FEATURE_SCHEMA_VERSION
from backend.app.services.drct_training_case_service import TrainingCaseService, TrainingDatasetBuild


QUALITY_THRESHOLDS = {"rule_match_rate": 70.0, "core_coverage": 80.0, "enriched_coverage": 60.0, "d20_coverage": 70.0}
SCORE_BUCKETS = ((0, 60, "0~59"), (60, 70, "60~69"), (70, 80, "70~79"), (80, 90, "80~89"), (90, 101, "90~100"))


class DrctSignalValidationService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _ratio(numerator: int, denominator: int) -> float | None:
        return numerator / denominator * 100 if denominator else None

    @classmethod
    def _gate(cls, build: TrainingDatasetBuild) -> dict[str, Any]:
        cases = build.cases
        reviewed_cases = [case for case in cases if case["label"] != "UNDECIDED"]
        matched_reviewed = [case for case in cases if case["label"] in {"SUCCESS", "FAILURE"} and case["rule_status"] == "RULE_MATCH"]
        evaluable = build.summary["rule_evaluable_count"]
        matched = build.summary["rule_matched_count"]
        values = {
            "reviewed_coverage": cls._metric(len(reviewed_cases), len(cases)),
            "rule_match_rate": cls._metric(matched, evaluable),
            "core_coverage": cls._metric(build.summary["core_ready_count"], matched),
            "enriched_coverage": cls._metric(build.summary["enriched_ready_count"], matched),
            "d20_coverage": cls._metric(sum(case["outcomes"].get("d20_return") is not None for case in matched_reviewed), len(matched_reviewed)),
        }
        warnings = []
        for key, threshold in QUALITY_THRESHOLDS.items():
            if values[key]["value"] is not None and values[key]["value"] < threshold:
                warnings.append({"code": f"LOW_{key.upper()}", "metric": key, "threshold": threshold, "actual": values[key]["value"]})
        return {**values, "warnings": warnings, "thresholds": QUALITY_THRESHOLDS}

    @classmethod
    def _metric(cls, numerator: int, denominator: int) -> dict[str, Any]:
        return {"value": cls._ratio(numerator, denominator), "numerator": numerator, "denominator": denominator}

    @staticmethod
    def _outcome(cases: list[dict[str, Any]], label: str) -> dict[str, Any]:
        selected = [case for case in cases if case["label"] == label and case["rule_status"] == "RULE_MATCH"]
        result: dict[str, Any] = {"case_count": len(selected)}
        for key in ("d5_return", "d10_return", "d20_return", "mfe_20", "mae_20"):
            values = [float(case["outcomes"][key]) for case in selected if case["outcomes"].get(key) is not None]
            result[key] = {"mean": float(np.mean(values)) if values else None, "median": float(np.median(values)) if values else None, "n": len(values)}
        return result

    @staticmethod
    def _difference(success: dict[str, Any], failure: dict[str, Any]) -> dict[str, float | None]:
        result = {}
        for key in ("d5_return", "d10_return", "d20_return", "mfe_20", "mae_20"):
            left, right = success[key]["mean"], failure[key]["mean"]
            result[key] = left - right if left is not None and right is not None else None
        return result

    @staticmethod
    def _case_index(cases: list[dict[str, Any]]) -> dict[tuple[int, str], dict[str, Any]]:
        return {(case["stock_id"], case["d0"]): case for case in cases}

    @classmethod
    def _buckets(cls, scores: list[dict[str, Any]], score_key: str, cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
        indexed = cls._case_index(cases)
        result = []
        for low, high, label in SCORE_BUCKETS:
            selected = [item for item in scores if low <= float(item[score_key]) < high]
            if not selected:
                continue
            related = [indexed[(int(item["stock_id"]), str(item["d0"]))] for item in selected]
            row: dict[str, Any] = {
                "bucket": label, "n": len(selected),
                "observed_success_ratio": sum(item["label"] == "SUCCESS" for item in selected) / len(selected) * 100,
            }
            for outcome in ("d20_return", "mfe_20", "mae_20"):
                values = [float(case["outcomes"][outcome]) for case in related if case["outcomes"].get(outcome) is not None]
                row[outcome] = float(np.mean(values)) if values else None
                if outcome == "d20_return": row["d20_median"] = float(np.median(values)) if values else None
            result.append(row)
        return result

    @staticmethod
    def _rank(values: np.ndarray) -> np.ndarray:
        order = np.argsort(values, kind="mergesort")
        ranks = np.empty(len(values), dtype=float)
        start = 0
        while start < len(values):
            end = start + 1
            while end < len(values) and values[order[end]] == values[order[start]]: end += 1
            ranks[order[start:end]] = (start + end - 1) / 2
            start = end
        return ranks

    @classmethod
    def _score_relationship(cls, prototype: list[dict[str, Any]], logistic: list[dict[str, Any]]) -> dict[str, Any]:
        left = {(item["stock_id"], item["d0"]): item for item in prototype}
        pairs = [(left[(item["stock_id"], item["d0"])]["prototype_score"], item["shadow_score"]) for item in logistic if (item["stock_id"], item["d0"]) in left]
        if len(pairs) < 2:
            return {"matched_case_count": len(pairs), "pearson": None, "spearman": None}
        x, y = np.asarray(pairs, dtype=float).T
        if np.std(x) < 1e-12 or np.std(y) < 1e-12:
            return {"matched_case_count": len(pairs), "pearson": None, "spearman": None}
        return {"matched_case_count": len(pairs), "pearson": float(np.corrcoef(x, y)[0, 1]), "spearman": float(np.corrcoef(cls._rank(x), cls._rank(y))[0, 1])}

    @staticmethod
    def _feature_research(cases: list[dict[str, Any]], profile: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        eligible = PatternBaselineService._eligible(cases, profile)
        success = [case for case in eligible if case["label"] == "SUCCESS"]
        failure = [case for case in eligible if case["label"] == "FAILURE"]
        if not success or not failure:
            return [], []
        key = "enriched_features" if profile == "ENRICHED" else "core_features"
        names = list(ENRICHED_FEATURE_NAMES if profile == "ENRICHED" else CORE_FEATURE_NAMES)
        distributions = []
        for name in names:
            s = np.asarray([case[key][name] for case in success], dtype=float)
            f = np.asarray([case[key][name] for case in failure], dtype=float)
            distributions.append({"feature": name, "success_median": float(np.median(s)), "failure_median": float(np.median(f)), "difference": float(np.median(s) - np.median(f)), "success_iqr": float(np.percentile(s, 75) - np.percentile(s, 25)), "failure_iqr": float(np.percentile(f, 75) - np.percentile(f, 25))})
        matrix = np.asarray([[case[key][name] for name in names] for case in eligible], dtype=float)
        correlations = []
        if len(eligible) >= 3:
            corr = np.corrcoef(matrix, rowvar=False)
            for left in range(len(names)):
                for right in range(left + 1, len(names)):
                    value = float(corr[left, right])
                    if np.isfinite(value) and abs(value) >= .90:
                        correlations.append({"feature_a": names[left], "feature_b": names[right], "correlation": value})
        return distributions, sorted(correlations, key=lambda item: abs(item["correlation"]), reverse=True)[:30]

    @staticmethod
    def _case_summary(case: dict[str, Any], reason: str, scores: dict[str, float] | None = None) -> dict[str, Any]:
        failed = [condition for condition in case.get("rule_diagnostics", []) if condition.get("status") in {"FAIL", "DATA_INCOMPLETE"}]
        return {
            "stock_id": case["stock_id"], "stock_code": case["stock_code"], "stock_name": case["stock_name"], "d0": case["d0"],
            "label": case["label"], "matched_marker_names": case["matched_marker_names"], "reason": reason,
            "rule_status": case["rule_status"], "core_status": case["core_status"], "enriched_status": case["enriched_status"],
            "failed_conditions": failed, "missing": list(dict.fromkeys(case.get("core_missing", []) + case.get("enriched_missing", []))),
            "d20_return": case["outcomes"].get("d20_return"), **(scores or {}),
        }

    @staticmethod
    def _research_status(build: TrainingDatasetBuild, profile: str) -> str:
        if build.summary["blocking_reasons"]: return "NOT_READY"
        if build.summary["rule_match_rate"] is not None and build.summary["rule_match_rate"] < QUALITY_THRESHOLDS["rule_match_rate"]: return "RULE_REVIEW_NEEDED"
        eligible = PatternBaselineService._eligible(build.cases, profile)
        if sum(case["label"] == "SUCCESS" for case in eligible) < PROTOTYPE_MIN_SUCCESS: return "DATA_TOO_SMALL"
        return "BASELINE_TESTABLE"

    def overview(self) -> dict[str, Any]:
        rows = self.db.execute(text("SELECT id, name FROM drct_signal_searches ORDER BY display_order, id")).mappings().all()
        items = []
        for row in rows:
            build = TrainingCaseService(self.db).build(int(row["id"]))
            profile = PatternBaselineService.choose_profile(build.cases, "AUTO")
            eligible = PatternBaselineService._eligible(build.cases, profile)
            success = sum(case["label"] == "SUCCESS" for case in eligible)
            failure = sum(case["label"] == "FAILURE" for case in eligible)
            baseline_possible = success >= PROTOTYPE_MIN_SUCCESS or (success >= LOGISTIC_MIN_SUCCESS and failure >= LOGISTIC_MIN_FAILURE and len(eligible) >= LOGISTIC_MIN_TOTAL)
            items.append({"search_id": build.search_id, "search_name": row["name"], "search_version_id": build.search_version_id, "version_no": build.version_no, "rule_valid": build.rule_status == "VALID", "marker_linked": build.marker_link_count > 0, "dataset_ready": not build.summary["blocking_reasons"] and build.summary["core_ready_count"] > 0, "baseline_possible": baseline_possible, "research_status": self._research_status(build, profile), "success_count": success, "failure_count": failure})
        return {"registered_search_count": len(items), "rule_valid_count": sum(item["rule_valid"] for item in items), "marker_linked_count": sum(item["marker_linked"] for item in items), "dataset_ready_count": sum(item["dataset_ready"] for item in items), "baseline_possible_count": sum(item["baseline_possible"] for item in items), "items": items}

    def report(self, search_id: int, search_version_id: int | None, requested_profile: str) -> dict[str, Any]:
        started = time.perf_counter()
        build = TrainingCaseService(self.db).build(search_id, search_version_id)
        profile = PatternBaselineService.choose_profile(build.cases, requested_profile)
        prototype = PatternBaselineService.prototype_shadow(build.cases, profile)
        logistic = PatternBaselineService.logistic_shadow(build.cases, profile)
        success_outcome = self._outcome(build.cases, "SUCCESS")
        failure_outcome = self._outcome(build.cases, "FAILURE")
        prototype_scores = prototype.get("case_scores", [])
        logistic_scores = logistic.get("case_scores", [])
        score_by_case: dict[tuple[int, str], dict[str, float]] = {}
        for item in prototype_scores: score_by_case.setdefault((item["stock_id"], item["d0"]), {})["prototype_score"] = item["prototype_score"]
        for item in logistic_scores: score_by_case.setdefault((item["stock_id"], item["d0"]), {})["shadow_score"] = item["shadow_score"]
        mismatch = [self._case_summary(case, "RULE_NO_MATCH") for case in build.cases if case["rule_status"] == "RULE_NO_MATCH"]
        incomplete = [self._case_summary(case, "DATA_INCOMPLETE") for case in build.cases if case["rule_status"] == "RULE_DATA_INCOMPLETE" or case["core_status"] != "READY" or case["enriched_status"] != "READY"]
        disagreements = []
        for case in build.cases:
            scores = score_by_case.get((case["stock_id"], case["d0"]), {})
            if case["label"] == "FAILURE" and (scores.get("prototype_score", -1) >= 80 or scores.get("shadow_score", -1) >= 80): reason = "HIGH_SCORE_FAILURE"
            elif case["label"] == "SUCCESS" and scores and max(scores.values()) < 60: reason = "LOW_SCORE_SUCCESS"
            else: continue
            disagreements.append(self._case_summary(case, reason, scores))
        distributions, correlations = self._feature_research(build.cases, profile)
        eligible = PatternBaselineService._eligible(build.cases, profile)
        quality_gate = self._gate(build)
        checklist = {"hts_reference_registered": True, "rule_valid": build.rule_status == "VALID", "marker_linked": build.marker_link_count > 0, "reviewed_case_exists": any(case["label"] in {"SUCCESS", "FAILURE"} for case in build.cases), "rule_match_exists": build.summary["rule_matched_count"] > 0, "core_ready": build.summary["core_ready_count"] > 0, "enriched_ready": build.summary["enriched_ready_count"] > 0}
        return {
            "metadata": {"search_id": build.search_id, "search_version_id": build.search_version_id, "version_no": build.version_no, "rule_schema_version": build.rule_schema_version, "feature_schema_version": FEATURE_SCHEMA_VERSION, "feature_profile": profile, "data_cutoff": build.summary["latest_d0"], "generated_at": datetime.now(timezone.utc).isoformat(), "training_case_count": len(eligible), "evaluated_case_count": max(prototype["evaluated_case_count"], logistic["evaluated_case_count"])},
            "research_status": self._research_status(build, profile), "checklist": checklist, "readiness": build.summary,
            "quality_gate": quality_gate,
            "labels": {"success_count": sum(case["label"] == "SUCCESS" for case in eligible), "failure_count": sum(case["label"] == "FAILURE" for case in eligible), "observed_success_ratio": self._ratio(sum(case["label"] == "SUCCESS" for case in eligible), len(eligible))},
            "outcomes": {"success": success_outcome, "failure": failure_outcome, "difference": self._difference(success_outcome, failure_outcome)},
            "prototype": {**prototype, "buckets": self._buckets(prototype_scores, "prototype_score", build.cases)},
            "logistic": {**logistic, "buckets": self._buckets(logistic_scores, "shadow_score", build.cases)},
            "score_relationship": self._score_relationship(prototype_scores, logistic_scores),
            "rule_mismatch_cases": mismatch, "data_incomplete_cases": incomplete, "model_disagreement_cases": disagreements,
            "feature_distribution": distributions, "high_correlation_pairs": correlations,
            "warnings": quality_gate["warnings"], "elapsed_ms": int((time.perf_counter() - started) * 1000),
        }
