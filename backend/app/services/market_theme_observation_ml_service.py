from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import math
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.pipeline import Pipeline
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.schemas.market_theme_observation_schema import (
    MarketThemeObservationAblationResult,
    MarketThemeObservationFeatureDiagnostic,
    MarketThemeObservationMLCandidate,
    MarketThemeObservationMLFoldResult,
    MarketThemeObservationMLMetrics,
    MarketThemeObservationMLTrainResponse,
)
from backend.app.services.market_theme_observation_feature_service import (
    OBSERVATION_FEATURE_NAMES,
    OBSERVATION_FEATURE_VERSION,
    PRICE_FLOW_FEATURE_NAMES,
    PRICE_FLOW_FEATURE_VERSION,
    MarketThemeObservationFeatureService,
)


FEATURE_GROUPS: dict[str, tuple[str, ...]] = {
    "PRICE": ("price_score", "base_change_rate", "return_"),
    "FLOW": ("flow_score", "foreign_flow", "institution_flow", "joint_flow", "program_flow", "combined_flow", "actor_direction", "flow_minus"),
    "FLOW_ACCELERATION": ("flow_acceleration", "flow_3d_minus_5d", "momentum_flow_interaction"),
    "BREADTH": ("breadth", "concentration", "alignment_breadth"),
    "TECHNICAL": ("technical_score", "alignment_score", "calendar_gap_days"),
    "MARKET": ("market_", "macro_"),
}

HGBC_BASE_PARAMS: dict[str, float | int | str] = {
    "learning_rate": 0.04, "max_iter": 120, "max_leaf_nodes": 12,
    "max_depth": 0, "min_samples_leaf": 20, "l2_regularization": 1.0,
}
HGBC_TUNING_PARAMS = (
    {"learning_rate": 0.03, "max_iter": 180, "max_leaf_nodes": 10, "max_depth": 5, "min_samples_leaf": 24, "l2_regularization": 1.5},
    {"learning_rate": 0.025, "max_iter": 220, "max_leaf_nodes": 15, "max_depth": 6, "min_samples_leaf": 30, "l2_regularization": 2.0},
)


def _ece(y_true: np.ndarray, probability: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0, 1, bins + 1)
    total = max(1, len(y_true))
    result = 0.0
    for index in range(bins):
        upper = probability < edges[index + 1] if index < bins - 1 else probability <= edges[index + 1]
        mask = (probability >= edges[index]) & upper
        if mask.any():
            result += float(mask.sum()) / total * abs(float(y_true[mask].mean()) - float(probability[mask].mean()))
    return result


def _rank_metrics(rows: list[dict[str, Any]], score_key: str) -> dict[str, float]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["target_date"])].append(row)
    collected: dict[str, list[float]] = defaultdict(list)
    for day_rows in grouped.values():
        ordered = sorted(day_rows, key=lambda row: (-float(row[score_key]), int(row["theme_id"])))
        actual = sorted(day_rows, key=lambda row: (int(row["label_rank"]), int(row["theme_id"])))
        actual_rank = {int(row["theme_id"]): index + 1 for index, row in enumerate(actual)}
        top_actual = {int(row["theme_id"]) for row in day_rows if int(row["label_top20"]) == 1}
        top_count = len(top_actual)
        top_pred = {int(row["theme_id"]) for row in ordered[:top_count]}
        hits = len(top_pred & top_actual)
        precision = hits / max(1, len(top_pred))
        recall = hits / max(1, len(top_actual))
        collected["precision_top20"].append(precision)
        collected["recall_top20"].append(recall)
        collected["f1_top20"].append(2 * precision * recall / (precision + recall) if precision + recall else 0)
        for top_n, key in ((5, "precision_at_5"), (10, "precision_at_10")):
            predicted = ordered[:top_n]
            collected[key].append(len({int(row["theme_id"]) for row in predicted} & top_actual) / max(1, min(top_n, len(ordered))))
        dcg = sum((1 if int(row["theme_id"]) in top_actual else 0) / math.log2(index + 2) for index, row in enumerate(ordered[:5]))
        idcg = sum(1 / math.log2(index + 2) for index in range(min(5, len(top_actual))))
        collected["ndcg_at_5"].append(dcg / idcg if idcg else 0)
        predicted_rank = {int(row["theme_id"]): index + 1 for index, row in enumerate(ordered)}
        count = len(ordered)
        if count > 1:
            collected["spearman"].append(1 - 6 * sum((predicted_rank[int(row["theme_id"])] - actual_rank[int(row["theme_id"])]) ** 2 for row in ordered) / (count * (count * count - 1)))
        collected["mean_rank_error"].append(sum(abs(predicted_rank[int(row["theme_id"])] - actual_rank[int(row["theme_id"])]) for row in ordered) / max(1, count))
        top5 = ordered[:5]
        strengths = [float(row["label_return"]) for row in top5 if row.get("label_return") is not None]
        if strengths:
            collected["top5_mean_actual_strength"].append(float(np.mean(strengths)))
        collected["top5_actual_top10_rate"].append(sum(int(row["label_rank"]) <= 10 for row in top5) / max(1, len(top5)))
        collected["top5_bottom_half_rate"].append(sum(int(row["label_rank"]) > count / 2 for row in top5) / max(1, len(top5)))
    return {key: float(np.mean(values)) for key, values in collected.items() if values}


def _feature_group(name: str) -> str:
    for group in ("FLOW_ACCELERATION", "MARKET", "BREADTH", "TECHNICAL", "FLOW", "PRICE"):
        if any(token in name for token in FEATURE_GROUPS[group]):
            return group
    return "OTHER"


def _structural_role(name: str) -> str:
    if "acceleration" in name or "minus" in name:
        return "ACCELERATION"
    if "momentum" in name:
        return "DIRECTION"
    if "streak" in name or "mean_" in name:
        return "PERSISTENCE"
    if name.startswith("macro_") or name.startswith("market_") or "environment" in name:
        return "REGIME"
    if "penalty" in name or "concentration" in name or "volatility" in name:
        return "OVERHEAT_EXHAUSTION"
    return "LEVEL"


def _day_rank_scale(rows: list[dict[str, Any]], key: str) -> dict[tuple[str, int], float]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["target_date"])].append(row)
    result: dict[tuple[str, int], float] = {}
    for day, day_rows in grouped.items():
        ordered = sorted(day_rows, key=lambda row: (float(row[key]), int(row["theme_id"])))
        denominator = max(1, len(ordered) - 1)
        for index, row in enumerate(ordered):
            result[(day, int(row["theme_id"]))] = index / denominator
    return result


class MarketThemeObservationMLService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _folds(dates: list[str], count: int = 4) -> list[tuple[list[str], list[str]]]:
        start = max(8, len(dates) // 2)
        remaining = dates[start:]
        if not remaining:
            return []
        size = max(1, math.ceil(len(remaining) / count))
        folds: list[tuple[list[str], list[str]]] = []
        for index in range(0, len(remaining), size):
            validation = remaining[index:index + size]
            training = dates[:start + index]
            if validation and len(training) >= 8:
                folds.append((training, validation))
        return folds

    @staticmethod
    def _model(parameters: dict[str, float | int | str]) -> Pipeline:
        depth = int(parameters.get("max_depth", 0))
        return Pipeline([
            ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
            ("model", HistGradientBoostingClassifier(
                learning_rate=float(parameters["learning_rate"]), max_iter=int(parameters["max_iter"]),
                max_leaf_nodes=int(parameters["max_leaf_nodes"]), max_depth=depth or None,
                min_samples_leaf=int(parameters["min_samples_leaf"]), l2_regularization=float(parameters["l2_regularization"]), random_state=42,
            )),
        ])

    @staticmethod
    def _weights(rows: list[Any], train_dates: list[str], mode: str) -> np.ndarray | None:
        if mode == "EQUAL":
            return None
        date_index = {day: index for index, day in enumerate(train_dates)}
        span = max(1, len(train_dates) - 1)
        strength = 0.5 if mode == "MILD" else 1.0
        return np.asarray([1 - strength / 2 + strength * date_index[row.base_date] / span for row in rows], dtype=float)

    @staticmethod
    def _row(item: Any, score: float, raw_score: float | None = None) -> dict[str, Any]:
        return {
            "base_date": item.base_date, "target_date": item.target_date, "theme_id": item.theme_id, "label_rank": item.label_rank,
            "label_top20": item.label_top20, "label_return": item.label_return,
            "score": float(score), "raw_score": float(raw_score if raw_score is not None else score), "rule": float(item.observation_rule_score),
        }

    def _predict_fold(self, by_date: dict[str, list[Any]], feature_names: list[str], train_dates: list[str], validation_dates: list[str], parameters: dict[str, float | int | str], weight_mode: str) -> tuple[list[dict[str, Any]], list[int], list[float], list[float]]:
        calibration_size = max(2, math.ceil(len(train_dates) * .20))
        model_dates = train_dates[:-calibration_size]
        calibration_dates = train_dates[-calibration_size:]
        model_rows = [row for day in model_dates for row in by_date[day]]
        calibration_rows = [row for day in calibration_dates for row in by_date[day]]
        validation_rows = [row for day in validation_dates for row in by_date[day]]
        x_model = np.asarray([[row.values.get(name) for name in feature_names] for row in model_rows], dtype=float)
        y_model = np.asarray([row.label_top20 for row in model_rows], dtype=int)
        x_calibration = np.asarray([[row.values.get(name) for name in feature_names] for row in calibration_rows], dtype=float)
        y_calibration = np.asarray([row.label_top20 for row in calibration_rows], dtype=int)
        x_validation = np.asarray([[row.values.get(name) for name in feature_names] for row in validation_rows], dtype=float)
        y_validation = np.asarray([row.label_top20 for row in validation_rows], dtype=int)
        if len(np.unique(y_model)) < 2 or len(np.unique(y_calibration)) < 2 or not validation_rows:
            return [], [], [], []
        model = self._model(parameters)
        weights = self._weights(model_rows, model_dates, weight_mode)
        fit_options = {} if weights is None else {"model__sample_weight": weights}
        model.fit(x_model, y_model, **fit_options)
        calibration_raw = np.clip(model.predict_proba(x_calibration)[:, 1], 1e-6, 1 - 1e-6)
        calibrator = LogisticRegression(C=1e6, max_iter=1000, random_state=42).fit(np.log(calibration_raw / (1 - calibration_raw)).reshape(-1, 1), y_calibration)
        validation_raw = np.clip(model.predict_proba(x_validation)[:, 1], 1e-6, 1 - 1e-6)
        validation_calibrated = np.clip(calibrator.predict_proba(np.log(validation_raw / (1 - validation_raw)).reshape(-1, 1))[:, 1], 1e-6, 1 - 1e-6)
        predictions = [self._row(row, probability, raw) for row, probability, raw in zip(validation_rows, validation_calibrated, validation_raw)]
        return predictions, y_validation.tolist(), validation_raw.tolist(), validation_calibrated.tolist()

    @staticmethod
    def _baseline_rows(by_date: dict[str, list[Any]], folds: list[tuple[list[str], list[str]]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for _, validation_dates in folds:
            for day in validation_dates:
                for item in by_date[day]:
                    rows.append({
                        "base_date": item.base_date, "target_date": item.target_date, "theme_id": item.theme_id, "label_rank": item.label_rank,
                        "label_top20": item.label_top20, "label_return": item.label_return,
                        "current": float(item.values.get("base_return_percentile") or 0), "momentum": float(item.values.get("return_3d_percentile") or 0),
                        "rule": float(item.observation_rule_score),
                    })
        return rows

    def _evaluate_candidate(self, name: str, by_date: dict[str, list[Any]], folds: list[tuple[list[str], list[str]]], feature_names: list[str], parameters: dict[str, float | int | str], weight_mode: str, rule_metrics: MarketThemeObservationMLMetrics, *, feature_version: str = OBSERVATION_FEATURE_VERSION) -> tuple[MarketThemeObservationMLCandidate, list[dict[str, Any]]]:
        predictions: list[dict[str, Any]] = []
        fold_results: list[MarketThemeObservationMLFoldResult] = []
        raw_y: list[int] = []
        raw_probability: list[float] = []
        calibrated_probability: list[float] = []
        for fold_index, (train_dates, validation_dates) in enumerate(folds, start=1):
            fold_rows, y_true, raw, calibrated = self._predict_fold(by_date, feature_names, train_dates, validation_dates, parameters, weight_mode)
            if not fold_rows:
                continue
            predictions.extend(fold_rows); raw_y.extend(y_true); raw_probability.extend(raw); calibrated_probability.extend(calibrated)
            metrics = MarketThemeObservationMLMetrics(**_rank_metrics(fold_rows, "score"))
            rule_fold_rows = [self._row(row, row.observation_rule_score) for day in validation_dates for row in by_date[day]]
            rule_fold = _rank_metrics(rule_fold_rows, "score")
            fold_results.append(MarketThemeObservationMLFoldResult(
                fold=fold_index, train_start_date=train_dates[0], train_end_date=train_dates[-1], validation_start_date=validation_dates[0], validation_end_date=validation_dates[-1],
                metrics=metrics, delta_precision_at_5=float(metrics.precision_at_5 or 0) - float(rule_fold.get("precision_at_5", 0)),
            ))
        ranked = _rank_metrics(predictions, "score")
        metrics = MarketThemeObservationMLMetrics(**ranked)
        y = np.asarray(raw_y, dtype=int); raw = np.asarray(raw_probability, dtype=float); calibrated = np.asarray(calibrated_probability, dtype=float)
        if len(y):
            metrics.brier = brier_score_loss(y, calibrated); metrics.log_loss = log_loss(y, calibrated); metrics.calibration_error = _ece(y, calibrated)
            metrics.raw_brier = brier_score_loss(y, raw); metrics.raw_log_loss = log_loss(y, raw); metrics.raw_calibration_error = _ece(y, raw)
        fold_p5 = [float(fold.metrics.precision_at_5 or 0) for fold in fold_results]
        version_tag = "V3" if feature_version == PRICE_FLOW_FEATURE_VERSION else "V2"
        calibration_error = metrics.calibration_error if metrics.calibration_error is not None else 1.0
        calibrated_brier = metrics.brier if metrics.brier is not None else 1.0
        raw_brier = metrics.raw_brier if metrics.raw_brier is not None else 0.0
        candidate = MarketThemeObservationMLCandidate(
            model_type=name, model_version=f"OBS-{name}-{version_tag}-{datetime.now().strftime('%Y%m%d%H%M%S')}", target_type="TOP20_RELATIVE_STRENGTH",
            selection_gate_status="NOT_EVALUATED", calibration_status="PASS" if float(calibration_error) <= .15 and float(calibrated_brier) <= float(raw_brier) + .01 else "FAIL",
            probability_display_mode="PROBABILITY", improving_fold_count=sum(float(fold.delta_precision_at_5 or 0) > 0 for fold in fold_results), validation_fold_count=len(fold_results),
            metrics=metrics, parameters={**parameters, "recent_weight": weight_mode}, feature_version=feature_version,
            delta_precision_at_5=float(metrics.precision_at_5 or 0) - float(rule_metrics.precision_at_5 or 0), delta_ndcg_at_5=float(metrics.ndcg_at_5 or 0) - float(rule_metrics.ndcg_at_5 or 0),
            fold_results=fold_results, worst_fold_precision_at_5=min(fold_p5) if fold_p5 else None, fold_precision_at_5_std=float(np.std(fold_p5)) if fold_p5 else None,
        )
        return candidate, predictions

    @staticmethod
    def _hybrid_candidate(name: str, rule_weight: float, model_rows: list[dict[str, Any]], folds: list[tuple[list[str], list[str]]], rule_metrics: MarketThemeObservationMLMetrics) -> MarketThemeObservationMLCandidate:
        rule_scale = _day_rank_scale(model_rows, "rule"); model_scale = _day_rank_scale(model_rows, "score")
        blended = [{**row, "hybrid": rule_weight * rule_scale[(str(row["target_date"]), int(row["theme_id"]))] + (1 - rule_weight) * model_scale[(str(row["target_date"]), int(row["theme_id"]))]} for row in model_rows]
        fold_results: list[MarketThemeObservationMLFoldResult] = []
        for fold_index, (train_dates, validation_dates) in enumerate(folds, start=1):
            fold_rows = [row for row in blended if row["base_date"] in validation_dates]
            metrics = MarketThemeObservationMLMetrics(**_rank_metrics(fold_rows, "hybrid")); rule_fold = _rank_metrics(fold_rows, "rule")
            fold_results.append(MarketThemeObservationMLFoldResult(
                fold=fold_index, train_start_date=train_dates[0], train_end_date=train_dates[-1], validation_start_date=validation_dates[0], validation_end_date=validation_dates[-1],
                metrics=metrics, delta_precision_at_5=float(metrics.precision_at_5 or 0) - float(rule_fold.get("precision_at_5", 0)),
            ))
        metrics = MarketThemeObservationMLMetrics(**_rank_metrics(blended, "hybrid")); fold_p5 = [float(fold.metrics.precision_at_5 or 0) for fold in fold_results]
        return MarketThemeObservationMLCandidate(
            model_type=name, target_type="TOP20_RELATIVE_STRENGTH", selection_gate_status="NOT_EVALUATED", calibration_status="NOT_APPLICABLE", probability_display_mode="SCORE",
            improving_fold_count=sum(float(fold.delta_precision_at_5 or 0) > 0 for fold in fold_results), validation_fold_count=len(fold_results), metrics=metrics, candidate_type="HYBRID",
            parameters={"rule_weight": rule_weight, "ml_weight": 1 - rule_weight, "normalization": "DATE_LOCAL_RANK"},
            delta_precision_at_5=float(metrics.precision_at_5 or 0) - float(rule_metrics.precision_at_5 or 0), delta_ndcg_at_5=float(metrics.ndcg_at_5 or 0) - float(rule_metrics.ndcg_at_5 or 0),
            fold_results=fold_results, worst_fold_precision_at_5=min(fold_p5) if fold_p5 else None, fold_precision_at_5_std=float(np.std(fold_p5)) if fold_p5 else None,
        )

    @staticmethod
    def _diagnostics(rows: list[Any], feature_names: list[str]) -> list[MarketThemeObservationFeatureDiagnostic]:
        result: list[MarketThemeObservationFeatureDiagnostic] = []
        for name in feature_names:
            raw = [row.values.get(name) for row in rows]
            valid = [round(float(value), 10) for value in raw if value is not None and math.isfinite(float(value))]
            unique = len(set(valid))
            result.append(MarketThemeObservationFeatureDiagnostic(
                feature_name=name, feature_group=_feature_group(name), structural_role=_structural_role(name), missing_rate=1 - len(valid) / max(1, len(raw)), unique_count=unique, near_constant=unique <= 1,
            ))
        return result

    @staticmethod
    def _apply_gate(candidates: list[MarketThemeObservationMLCandidate], baseline_metrics: dict[str, MarketThemeObservationMLMetrics], fold_count: int) -> None:
        best_baseline_top20 = max(float(metric.precision_top20 or 0) for metric in baseline_metrics.values())
        best_baseline_ndcg = max(float(metric.ndcg_at_5 or 0) for metric in baseline_metrics.values())
        for candidate in candidates:
            rank_pass = float(candidate.metrics.precision_top20 or 0) >= best_baseline_top20 + .03 and float(candidate.metrics.ndcg_at_5 or 0) >= best_baseline_ndcg
            stable = candidate.improving_fold_count >= math.ceil(fold_count / 2)
            passed = rank_pass and stable and candidate.calibration_status == "PASS"
            candidate.selection_gate_status = "PASS" if passed else "FAIL"; candidate.candidate_status = "CANDIDATE" if passed else "EXPERIMENTAL"

    def _attach_oos(self, candidate: MarketThemeObservationMLCandidate, by_date: dict[str, list[Any]], development_dates: list[str], oos_dates: list[str], feature_names: list[str]) -> list[dict[str, Any]]:
        parameters = {key: value for key, value in candidate.parameters.items() if key in HGBC_BASE_PARAMS}
        rows, _, _, _ = self._predict_fold(by_date, feature_names, development_dates, oos_dates, parameters, str(candidate.parameters.get("recent_weight", "EQUAL")))
        candidate.oos_metrics = MarketThemeObservationMLMetrics(**_rank_metrics(rows, "score")) if rows else None
        return rows

    def train(self) -> MarketThemeObservationMLTrainResponse:
        dataset = MarketThemeObservationFeatureService(self.db).build_dataset()
        labeled = [row for row in dataset.rows if row.label_top20 is not None and row.label_rank is not None]
        dates = sorted({row.base_date for row in labeled})
        oos_count = 21 if len(dates) >= 60 else 0
        development_dates = dates[:-oos_count] if oos_count else dates
        oos_dates = dates[-oos_count:] if oos_count else []
        folds = self._folds(development_dates)
        if not folds:
            return MarketThemeObservationMLTrainResponse(status="INSUFFICIENT_DATA", message="walk-forward 검증 날짜가 부족합니다.", feature_version=OBSERVATION_FEATURE_VERSION, distinct_base_dates=len(dates), train_row_count=len(labeled), qualified_date_count=len(dataset.qualified_dates), excluded_universe_dates=dataset.excluded_universe_dates)
        by_date: dict[str, list[Any]] = defaultdict(list)
        for row in labeled:
            by_date[row.base_date].append(row)
        feature_names = list(OBSERVATION_FEATURE_NAMES)
        baseline_rows = self._baseline_rows(by_date, folds)
        baseline_metrics = {name: MarketThemeObservationMLMetrics(**_rank_metrics(baseline_rows, key)) for name, key in (("CURRENT_RANK", "current"), ("MOMENTUM_3D", "momentum"), ("OBSERVATION_RULE", "rule"))}
        rule_metrics = baseline_metrics["OBSERVATION_RULE"]
        baseline_fold_results: list[MarketThemeObservationMLFoldResult] = []
        for index, (train_dates, validation_dates) in enumerate(folds, start=1):
            rows = [row for row in baseline_rows if row["base_date"] in validation_dates]
            baseline_fold_results.append(MarketThemeObservationMLFoldResult(fold=index, train_start_date=train_dates[0], train_end_date=train_dates[-1], validation_start_date=validation_dates[0], validation_end_date=validation_dates[-1], metrics=MarketThemeObservationMLMetrics(**_rank_metrics(rows, "rule")), delta_precision_at_5=0))

        v3_feature_names = list(PRICE_FLOW_FEATURE_NAMES)
        evaluated: list[tuple[MarketThemeObservationMLCandidate, list[dict[str, Any]], list[str]]] = []
        for name, selected_features, weight_mode, version in (
            ("HGBC_BASE_V2", feature_names, "EQUAL", OBSERVATION_FEATURE_VERSION),
            ("HGBC_RECENT_MILD_V2", feature_names, "MILD", OBSERVATION_FEATURE_VERSION),
            ("PRICE_FLOW_V3_BASE", v3_feature_names, "EQUAL", PRICE_FLOW_FEATURE_VERSION),
            ("PRICE_FLOW_V3_RECENT_MILD", v3_feature_names, "MILD", PRICE_FLOW_FEATURE_VERSION),
        ):
            candidate, predictions = self._evaluate_candidate(
                name, by_date, folds, selected_features, HGBC_BASE_PARAMS, weight_mode, rule_metrics,
                feature_version=version,
            )
            evaluated.append((candidate, predictions, selected_features))

        v3_base = next(item[0] for item in evaluated if item[0].model_type == "PRICE_FLOW_V3_BASE")
        ablation_groups = {
            "FULL_V3": set(),
            "-price_flow_gap": {"price_flow_gap"},
            "-flow_acceleration": {"flow_acceleration", "flow_acceleration_percentile", "flow_3d_minus_5d", "momentum_flow_interaction"},
            "-flow_continuity": {"joint_positive_streak", "flow_persistence_percentile"},
            "-breadth": {"breadth_score", "breadth_percentile", "price_breadth", "joint_flow_breadth", "breadth_short_change", "breadth_flow_interaction", "alignment_breadth_interaction"},
            "-price_headroom": {"price_headroom_percentile"},
            "-concentration": {"top1_concentration", "top3_concentration", "concentration_inverse_percentile"},
            "-sustainability_composite": {"sustainability_score"},
        }
        ablation_results: list[MarketThemeObservationAblationResult] = []
        for group, removed in ablation_groups.items():
            if not removed:
                candidate = v3_base
            else:
                selected = [name for name in v3_feature_names if name not in removed]
                candidate, _ = self._evaluate_candidate(
                    f"PRICE_FLOW_V3{group}", by_date, folds, selected, HGBC_BASE_PARAMS, "EQUAL", rule_metrics,
                    feature_version=PRICE_FLOW_FEATURE_VERSION,
                )
            delta_p5 = float(candidate.metrics.precision_at_5 or 0) - float(v3_base.metrics.precision_at_5 or 0)
            delta_ndcg = float(candidate.metrics.ndcg_at_5 or 0) - float(v3_base.metrics.ndcg_at_5 or 0)
            delta_top20 = float(candidate.metrics.precision_top20 or 0) - float(v3_base.metrics.precision_top20 or 0)
            delta_failure = float(candidate.metrics.top5_bottom_half_rate or 0) - float(v3_base.metrics.top5_bottom_half_rate or 0)
            verdict = "예측 기여 높음" if delta_p5 < -.002 or delta_failure > .002 else "Noise 가능성" if delta_p5 > .002 and delta_failure <= 0 else "영향 제한적"
            ablation_results.append(MarketThemeObservationAblationResult(
                feature_group=group, metrics=candidate.metrics, delta_precision_at_5=delta_p5,
                delta_ndcg_at_5=delta_ndcg, delta_precision_top20=delta_top20,
                delta_top5_bottom_half_rate=delta_failure, verdict="기준" if group == "FULL_V3" else verdict,
            ))

        candidates = [item[0] for item in evaluated]
        self._apply_gate(candidates, baseline_metrics, len(folds))

        oos_prediction_sets: dict[str, list[dict[str, Any]]] = {}
        if oos_dates:
            for candidate, _, selected_features in evaluated:
                oos_prediction_sets[candidate.model_type] = self._attach_oos(candidate, by_date, development_dates, oos_dates, selected_features)
            oos_rule_rows = [self._row(row, row.observation_rule_score) for day in oos_dates for row in by_date[day]]
            baseline_metrics["OBSERVATION_RULE_OOS"] = MarketThemeObservationMLMetrics(**_rank_metrics(oos_rule_rows, "score"))

        development_set = set(development_dates)
        development_row_count = sum(row.base_date in development_set for row in labeled)
        for candidate in [item[0] for item in evaluated]:
            self._store(candidate, development_dates, development_row_count)
        self.db.commit()
        # OOS participates only in post-experiment ranking, never parameter fitting/tuning.
        # The conservative minimum prevents a high development score from hiding a recent regime collapse.
        ranked = sorted(candidates, key=lambda item: (
            min(float(item.metrics.precision_at_5 or 0), float(item.oos_metrics.precision_at_5 or 0)) if item.oos_metrics else float(item.metrics.precision_at_5 or 0),
            -float(item.fold_precision_at_5_std or 0), float(item.metrics.ndcg_at_5 or 0),
        ), reverse=True)
        passed = [candidate for candidate in ranked if candidate.selection_gate_status == "PASS"]
        recommendation = "Gate 통과 후보는 운영에 반영하지 않고 Shadow 검증을 권고합니다." if passed else "Gate 통과 후보가 없어 현 운영 Rule V2를 유지합니다."
        return MarketThemeObservationMLTrainResponse(
            status="COMPLETED", message="Feature V2와 PRICE_FLOW_V3의 Walk-forward·Ablation·최근 OOS 검증을 완료했습니다.", feature_version=PRICE_FLOW_FEATURE_VERSION,
            train_start_date=development_dates[0], train_end_date=development_dates[-1], distinct_base_dates=len(dates), train_row_count=development_row_count, qualified_date_count=len(dataset.qualified_dates), excluded_universe_dates=dataset.excluded_universe_dates,
            validation_fold_count=len(folds), candidates=ranked, baseline_metrics=baseline_metrics, baseline_fold_results=baseline_fold_results,
            feature_diagnostics=self._diagnostics([row for row in labeled if row.base_date in development_set], v3_feature_names), ablation_results=ablation_results,
            oos_start_date=oos_dates[0] if oos_dates else None, oos_end_date=oos_dates[-1] if oos_dates else None, oos_sample_days=len(oos_dates),
            recommended_candidate=ranked[0].model_type if ranked else None, recommendation=recommendation,
        )

    def _store(self, candidate: MarketThemeObservationMLCandidate, dates: list[str], row_count: int) -> None:
        metrics = candidate.metrics; now = datetime.now().isoformat(timespec="seconds")
        self.db.execute(text("""
            INSERT INTO market_theme_return_prediction_models
            (model_version,model_type,feature_version,status,trained_at,train_start_date,train_end_date,distinct_train_dates,
             train_row_count,validation_fold_count,artifact_path,created_at,updated_at,target_type,selection_gate_status,
             selection_reason,validation_improving_fold_count,metric_version,validation_precision_at_5,validation_spearman,
             validation_ndcg_at_5,validation_mean_rank_error,validation_precision_top20,validation_recall_top20,validation_f1_top20,
             validation_brier,validation_log_loss,validation_calibration_error,raw_validation_brier,raw_validation_log_loss,
             raw_validation_calibration_error,calibration_status,probability_display_mode)
            VALUES (:version,:kind,:feature,:status,:now,:start,:end,:dates,:rows,:folds,'',:now,:now,
                    'TOP20_RELATIVE_STRENGTH',:gate,:reason,:improving,'THEME_OBSERVATION_METRIC_V2',:p5,:spearman,:ndcg,:rank_error,
                    :p20,:r20,:f1,:brier,:log_loss,:ece,:raw_brier,:raw_log_loss,:raw_ece,:calibration,:display)
        """), {
            "version": candidate.model_version, "kind": candidate.model_type, "feature": candidate.feature_version, "status": candidate.candidate_status,
            "now": now, "start": dates[0], "end": dates[-1], "dates": len(dates), "rows": row_count, "folds": candidate.validation_fold_count,
            "gate": candidate.selection_gate_status, "reason": "Top20 +3%p·NDCG 비열화 없음·fold 안정성·보정 Gate", "improving": candidate.improving_fold_count,
            "p5": metrics.precision_at_5, "spearman": metrics.spearman, "ndcg": metrics.ndcg_at_5, "rank_error": metrics.mean_rank_error,
            "p20": metrics.precision_top20, "r20": metrics.recall_top20, "f1": metrics.f1_top20, "brier": metrics.brier, "log_loss": metrics.log_loss,
            "ece": metrics.calibration_error, "raw_brier": metrics.raw_brier, "raw_log_loss": metrics.raw_log_loss, "raw_ece": metrics.raw_calibration_error,
            "calibration": candidate.calibration_status, "display": candidate.probability_display_mode,
        })
