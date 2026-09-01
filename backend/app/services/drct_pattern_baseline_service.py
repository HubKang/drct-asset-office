from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np

from backend.app.services.drct_pattern_feature_service import CORE_FEATURE_NAMES, ENRICHED_FEATURE_NAMES, FEATURE_SCHEMA_VERSION


PROTOTYPE_MIN_SUCCESS = 5
LOGISTIC_MIN_SUCCESS = 5
LOGISTIC_MIN_FAILURE = 5
LOGISTIC_MIN_TOTAL = 15


class PatternBaselineService:
    @staticmethod
    def _eligible(cases: list[dict[str, Any]], profile: str) -> list[dict[str, Any]]:
        status_key = "enriched_status" if profile == "ENRICHED" else "core_status"
        return [case for case in cases if case["label"] in {"SUCCESS", "FAILURE"} and case["rule_status"] == "RULE_MATCH" and case[status_key] == "READY"]

    @classmethod
    def choose_profile(cls, cases: list[dict[str, Any]], requested: str) -> str:
        if requested in {"CORE", "ENRICHED"}: return requested
        enriched = cls._eligible(cases, "ENRICHED")
        success = sum(case["label"] == "SUCCESS" for case in enriched)
        failure = sum(case["label"] == "FAILURE" for case in enriched)
        return "ENRICHED" if success >= LOGISTIC_MIN_SUCCESS and failure >= LOGISTIC_MIN_FAILURE and len(enriched) >= LOGISTIC_MIN_TOTAL else "CORE"

    @staticmethod
    def _profile_values(cases: list[dict[str, Any]], profile: str) -> tuple[np.ndarray, list[str]]:
        names = list(ENRICHED_FEATURE_NAMES if profile == "ENRICHED" else CORE_FEATURE_NAMES)
        key = "enriched_features" if profile == "ENRICHED" else "core_features"
        return np.asarray([[float(case[key][name]) for name in names] for case in cases], dtype=float), names

    @staticmethod
    def _prototype_stats(values: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        median = np.median(values, axis=0)
        q25, q75 = np.percentile(values, [25, 75], axis=0)
        iqr = q75 - q25
        usable = iqr > 1e-12
        return median, iqr, usable

    @staticmethod
    def _similarity(row: np.ndarray, median: np.ndarray, iqr: np.ndarray, usable: np.ndarray) -> float:
        if not np.any(usable):
            return 100.0 if np.allclose(row, median) else 0.0
        distance = float(np.mean(np.abs((row[usable] - median[usable]) / iqr[usable])))
        return 100.0 / (1.0 + distance)

    @classmethod
    def prototype(cls, cases: list[dict[str, Any]], profile: str) -> dict[str, Any]:
        eligible = cls._eligible(cases, profile)
        success_cases = [case for case in eligible if case["label"] == "SUCCESS"]
        failure_cases = [case for case in eligible if case["label"] == "FAILURE"]
        if len(success_cases) < PROTOTYPE_MIN_SUCCESS:
            return {"status": "INSUFFICIENT_DATA", "success_count": len(success_cases), "failure_count": len(failure_cases), "score_summary": None, "failure_contrast": False, "case_scores": []}
        success_values, names = cls._profile_values(success_cases, profile)
        success_median, success_iqr, success_usable = cls._prototype_stats(success_values)
        failure_stats = None
        if len(failure_cases) >= LOGISTIC_MIN_FAILURE:
            failure_values, _ = cls._profile_values(failure_cases, profile)
            failure_stats = cls._prototype_stats(failure_values)
        all_values, _ = cls._profile_values(eligible, profile)
        scores = []
        for case, row in zip(eligible, all_values, strict=True):
            success_similarity = cls._similarity(row, success_median, success_iqr, success_usable)
            failure_similarity = None
            score = success_similarity
            if failure_stats is not None:
                failure_similarity = cls._similarity(row, *failure_stats)
                score = max(0.0, min(100.0, success_similarity + 0.25 * (success_similarity - failure_similarity)))
            scores.append({"stock_id": case["stock_id"], "d0": case["d0"], "label": case["label"], "score": score, "success_similarity": success_similarity, "failure_similarity": failure_similarity})
        by_label = {}
        for label in ("SUCCESS", "FAILURE"):
            values = [item["score"] for item in scores if item["label"] == label]
            by_label[label] = {"count": len(values), "average": float(np.mean(values)) if values else None, "median": float(np.median(values)) if values else None}
        return {
            "status": "READY", "success_count": len(success_cases), "failure_count": len(failure_cases),
            "score_summary": by_label, "failure_contrast": failure_stats is not None,
            "feature_count": len(names), "zero_iqr_feature_count": int(np.sum(~success_usable)), "case_scores": scores,
        }

    @classmethod
    def prototype_shadow(cls, cases: list[dict[str, Any]], profile: str) -> dict[str, Any]:
        """Evaluate a success prototype only on date batches later than its training rows."""
        eligible = cls._eligible(cases, profile)
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for case in sorted(eligible, key=lambda item: (item["d0"], item["stock_id"])):
            grouped[case["d0"]].append(case)
        training: list[dict[str, Any]] = []
        evaluated: list[dict[str, Any]] = []
        initial_count = 0
        for d0 in sorted(grouped):
            batch = grouped[d0]
            success_training = [case for case in training if case["label"] == "SUCCESS"]
            if len(success_training) < PROTOTYPE_MIN_SUCCESS:
                initial_count += len(batch)
                training.extend(batch)
                continue
            success_values, _ = cls._profile_values(success_training, profile)
            success_stats = cls._prototype_stats(success_values)
            failure_training = [case for case in training if case["label"] == "FAILURE"]
            failure_stats = None
            if len(failure_training) >= LOGISTIC_MIN_FAILURE:
                failure_values, _ = cls._profile_values(failure_training, profile)
                failure_stats = cls._prototype_stats(failure_values)
            batch_values, _ = cls._profile_values(batch, profile)
            for case, row in zip(batch, batch_values, strict=True):
                success_similarity = cls._similarity(row, *success_stats)
                failure_similarity = cls._similarity(row, *failure_stats) if failure_stats is not None else None
                score = success_similarity if failure_similarity is None else max(0.0, min(100.0, success_similarity + 0.25 * (success_similarity - failure_similarity)))
                evaluated.append({"stock_id": case["stock_id"], "d0": case["d0"], "label": case["label"], "prototype_score": score})
            training.extend(batch)
        return {
            "status": "OOS_EVALUATED" if evaluated else "INSUFFICIENT_EVALUATION",
            "training_case_count": len(eligible), "evaluated_case_count": len(evaluated),
            "initial_training_window_count": initial_count, "case_scores": evaluated,
        }

    @staticmethod
    def _fit_logistic(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, float, np.ndarray, np.ndarray]:
        mean = x.mean(axis=0)
        scale = x.std(axis=0)
        scale[scale < 1e-12] = 1.0
        z = (x - mean) / scale
        weights = np.zeros(z.shape[1], dtype=float)
        intercept = 0.0
        learning_rate = 0.1
        l2 = 1.0
        for _ in range(600):
            logits = np.clip(z @ weights + intercept, -30, 30)
            probabilities = 1 / (1 + np.exp(-logits))
            error = probabilities - y
            weights -= learning_rate * ((z.T @ error) / len(y) + l2 * weights / len(y))
            intercept -= learning_rate * float(np.mean(error))
        return weights, intercept, mean, scale

    @staticmethod
    def _predict(x: np.ndarray, fitted: tuple[np.ndarray, float, np.ndarray, np.ndarray]) -> np.ndarray:
        weights, intercept, mean, scale = fitted
        logits = np.clip(((x - mean) / scale) @ weights + intercept, -30, 30)
        return 1 / (1 + np.exp(-logits))

    @staticmethod
    def _roc_auc(y: np.ndarray, scores: np.ndarray) -> float | None:
        positives, negatives = int(np.sum(y == 1)), int(np.sum(y == 0))
        if positives == 0 or negatives == 0: return None
        wins = 0.0
        for positive in scores[y == 1]:
            for negative in scores[y == 0]:
                wins += 1 if positive > negative else 0.5 if positive == negative else 0
        return wins / (positives * negatives)

    @classmethod
    def logistic_shadow(cls, cases: list[dict[str, Any]], profile: str) -> dict[str, Any]:
        eligible = cls._eligible(cases, profile)
        success_count = sum(case["label"] == "SUCCESS" for case in eligible)
        failure_count = sum(case["label"] == "FAILURE" for case in eligible)
        if success_count < LOGISTIC_MIN_SUCCESS or failure_count < LOGISTIC_MIN_FAILURE or len(eligible) < LOGISTIC_MIN_TOTAL:
            return {"status": "INSUFFICIENT_DATA", "training_case_count": len(eligible), "evaluated_case_count": 0, "initial_training_window_count": 0, "metrics": None, "feature_effects": []}
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for case in sorted(eligible, key=lambda item: (item["d0"], item["stock_id"])): grouped[case["d0"]].append(case)
        training: list[dict[str, Any]] = []
        evaluated: list[dict[str, Any]] = []
        window_directions: dict[str, list[str]] = defaultdict(list)
        initial_count = 0
        for d0 in sorted(grouped):
            batch = grouped[d0]
            train_success = sum(case["label"] == "SUCCESS" for case in training)
            train_failure = sum(case["label"] == "FAILURE" for case in training)
            if train_success >= LOGISTIC_MIN_SUCCESS and train_failure >= LOGISTIC_MIN_FAILURE:
                x_train, _ = cls._profile_values(training, profile)
                y_train = np.asarray([1.0 if case["label"] == "SUCCESS" else 0.0 for case in training])
                x_test, _ = cls._profile_values(batch, profile)
                fitted = cls._fit_logistic(x_train, y_train)
                probabilities = cls._predict(x_test, fitted)
                names = list(ENRICHED_FEATURE_NAMES if profile == "ENRICHED" else CORE_FEATURE_NAMES)
                for name, weight in zip(names, fitted[0], strict=True):
                    window_directions[name].append("SUCCESS" if weight > 0 else "FAILURE" if weight < 0 else "NEUTRAL")
                evaluated.extend({"stock_id": case["stock_id"], "d0": case["d0"], "label": case["label"], "shadow_score": float(score * 100)} for case, score in zip(batch, probabilities, strict=True))
            else:
                initial_count += len(batch)
            training.extend(batch)
        if not evaluated:
            return {"status": "INSUFFICIENT_EVALUATION", "training_case_count": len(eligible), "evaluated_case_count": 0, "initial_training_window_count": initial_count, "metrics": None, "feature_effects": [], "coefficient_stability": []}
        y_true = np.asarray([1 if item["label"] == "SUCCESS" else 0 for item in evaluated])
        probability = np.asarray([item["shadow_score"] / 100 for item in evaluated])
        predicted = (probability >= 0.5).astype(int)
        predicted_positive = int(np.sum(predicted == 1))
        actual_positive = int(np.sum(y_true == 1))
        true_positive = int(np.sum((predicted == 1) & (y_true == 1)))
        metrics = {
            "accuracy": float(np.mean(predicted == y_true)),
            "precision": true_positive / predicted_positive if predicted_positive else None,
            "recall": true_positive / actual_positive if actual_positive else None,
            "roc_auc": cls._roc_auc(y_true, probability),
            "brier_score": float(np.mean((probability - y_true) ** 2)),
        }
        x_all, names = cls._profile_values(eligible, profile)
        y_all = np.asarray([1.0 if case["label"] == "SUCCESS" else 0.0 for case in eligible])
        weights, _intercept, _mean, _scale = cls._fit_logistic(x_all, y_all)
        effects = sorted(({"feature": name, "coefficient": float(weight), "direction": "SUCCESS" if weight > 0 else "FAILURE" if weight < 0 else "NEUTRAL"} for name, weight in zip(names, weights, strict=True)), key=lambda item: abs(item["coefficient"]), reverse=True)
        stability = []
        for name in names:
            directions = window_directions.get(name, [])
            flips = sum(left != right for left, right in zip(directions, directions[1:]))
            stability.append({"feature": name, "window_count": len(directions), "direction_flip_count": flips, "stable": flips == 0})
        return {
            "status": "SHADOW_EVALUATED", "training_case_count": len(eligible), "evaluated_case_count": len(evaluated),
            "initial_training_window_count": initial_count, "metrics": metrics, "feature_effects": effects[:10], "coefficient_stability": stability, "case_scores": evaluated,
        }

    @classmethod
    def evaluate(cls, cases: list[dict[str, Any]], requested_profile: str) -> dict[str, Any]:
        profile = cls.choose_profile(cases, requested_profile)
        prototype = cls.prototype(cases, profile)
        logistic = cls.logistic_shadow(cases, profile)
        return {"feature_profile": profile, "feature_schema_version": FEATURE_SCHEMA_VERSION, "prototype": prototype, "logistic": logistic}
