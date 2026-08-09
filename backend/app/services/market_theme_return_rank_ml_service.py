from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import math
import os
from pathlib import Path
from typing import Any, Callable

import joblib
import numpy as np
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")
import sklearn
from fastapi import HTTPException, status
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.schemas.market_theme_return_prediction_schema import (
    MarketThemeReturnMLPerformanceWindow,
    MarketThemeReturnMLStatusResponse,
    MarketThemeReturnMLTrainResponse,
)
from backend.app.services.market_theme_return_feature_service import (
    FEATURE_NAMES_V2,
    FEATURE_VERSION_V2,
    MarketThemeReturnFeatureService,
    ThemeFeatureRow,
)


METRIC_VERSION = "THEME_RETURN_METRIC_V2"
MIN_TRAIN_DATES = 40
MIN_TRAIN_ROWS = 500
MIN_LIVE_REVIEW_RUNS = 20
DRIFT_NDCG_DEGRADED = 0.10
DRIFT_NDCG_WATCH = 0.05
DRIFT_MAE_DEGRADED_RATIO = 0.25
DRIFT_MAE_WATCH_RATIO = 0.10
ARTIFACT_DIR = Path(__file__).resolve().parents[2] / "model_artifacts" / "theme_return_prediction"


def _mean(values: list[float]) -> float | None:
    return float(np.mean(values)) if values else None


def rank_percentiles(rows: list[ThemeFeatureRow]) -> dict[tuple[str, int], float]:
    """Return deterministic, date-local percentiles: strongest=1 and weakest=0."""
    by_date: dict[str, list[ThemeFeatureRow]] = defaultdict(list)
    for row in rows:
        if row.target_date and row.label is not None:
            by_date[row.target_date].append(row)
    result: dict[tuple[str, int], float] = {}
    for target_date, group in by_date.items():
        ordered = sorted(group, key=lambda item: (-float(item.label), item.theme_id))
        denominator = max(1, len(ordered) - 1)
        for index, row in enumerate(ordered):
            result[(target_date, row.theme_id)] = 1.0 if len(ordered) == 1 else (len(ordered) - index - 1) / denominator
    return result


def top_k_labels(rows: list[ThemeFeatureRow], k: int = 5) -> dict[tuple[str, int], int]:
    by_date: dict[str, list[ThemeFeatureRow]] = defaultdict(list)
    for row in rows:
        if row.target_date and row.label is not None:
            by_date[row.target_date].append(row)
    result: dict[tuple[str, int], int] = {}
    for target_date, group in by_date.items():
        ordered = sorted(group, key=lambda item: (-float(item.label), item.theme_id))
        selected = {row.theme_id for row in ordered[:k]}
        result.update({(target_date, row.theme_id): int(row.theme_id in selected) for row in group})
    return result


def top_percent_labels(rows: list[ThemeFeatureRow], ratio: float = .20) -> dict[tuple[str, int], int]:
    by_date: dict[str, list[ThemeFeatureRow]] = defaultdict(list)
    for row in rows:
        if row.target_date and row.label is not None:
            by_date[row.target_date].append(row)
    result: dict[tuple[str, int], int] = {}
    for target_date, group in by_date.items():
        count = max(1, math.ceil(len(group) * ratio))
        ordered = sorted(group, key=lambda item: (-float(item.label), item.theme_id))
        selected = {row.theme_id for row in ordered[:count]}
        result.update({(target_date, row.theme_id): int(row.theme_id in selected) for row in group})
    return result


def _ndcg(predicted: list[int], actual: list[int], k: int) -> float | None:
    if len(predicted) < k or len(actual) < k:
        return None
    actual_rank = {theme_id: rank for rank, theme_id in enumerate(actual, 1)}
    relevance = {theme_id: max(0, len(actual) - rank + 1) for theme_id, rank in actual_rank.items()}
    dcg = sum((2 ** relevance.get(theme_id, 0) - 1) / math.log2(index + 2) for index, theme_id in enumerate(predicted[:k]))
    ideal = sum((2 ** relevance[theme_id] - 1) / math.log2(index + 2) for index, theme_id in enumerate(actual[:k]))
    return dcg / ideal if ideal else None


def evaluate_rank_predictions(
    rows: list[ThemeFeatureRow],
    rank_scores: list[float],
    predicted_returns: list[float] | None = None,
) -> dict[str, float | None]:
    """Metric V2: every ranking metric is calculated per target date, then date-averaged."""
    by_date: dict[str, list[tuple[ThemeFeatureRow, float, float | None]]] = defaultdict(list)
    for index, (row, score) in enumerate(zip(rows, rank_scores)):
        if row.target_date and row.label is not None:
            predicted_return = None if predicted_returns is None else float(predicted_returns[index])
            by_date[row.target_date].append((row, float(score), predicted_return))
    p_values: dict[int, list[float]] = {3: [], 5: [], 10: []}
    spearman: list[float] = []
    ndcg: list[float] = []
    rank_error: list[float] = []
    errors: list[float] = []
    directions: list[float] = []
    for pairs in by_date.values():
        predicted_order = [item[0].theme_id for item in sorted(pairs, key=lambda item: (-item[1], item[0].theme_id))]
        actual_order = [item[0].theme_id for item in sorted(pairs, key=lambda item: (-float(item[0].label), item[0].theme_id))]
        predicted_rank = {theme_id: rank for rank, theme_id in enumerate(predicted_order, 1)}
        actual_rank = {theme_id: rank for rank, theme_id in enumerate(actual_order, 1)}
        for k in (3, 5, 10):
            if len(pairs) >= k:
                p_values[k].append(len(set(predicted_order[:k]) & set(actual_order[:k])) / k)
        if len(pairs) > 1:
            d2 = sum((predicted_rank[theme_id] - actual_rank[theme_id]) ** 2 for theme_id in predicted_order)
            count = len(pairs)
            spearman.append(1 - 6 * d2 / (count * (count * count - 1)))
        value = _ndcg(predicted_order, actual_order, 5)
        if value is not None:
            ndcg.append(value)
        rank_error.extend(abs(predicted_rank[theme_id] - actual_rank[theme_id]) for theme_id in predicted_order)
        for row, _, prediction in pairs:
            if prediction is None:
                continue
            gap = float(row.label) - prediction
            errors.append(gap)
            actual_direction = 0 if abs(float(row.label)) <= .5 else (1 if float(row.label) > 0 else -1)
            predicted_direction = 0 if abs(prediction) <= .5 else (1 if prediction > 0 else -1)
            directions.append(float(actual_direction == predicted_direction))
    return {
        "mae": _mean([abs(value) for value in errors]),
        "rmse": math.sqrt(float(np.mean([value * value for value in errors]))) if errors else None,
        "mean_signed_gap": _mean(errors),
        "direction_accuracy": _mean(directions),
        "precision_at_3": _mean(p_values[3]),
        "precision_at_5": _mean(p_values[5]),
        "precision_at_10": _mean(p_values[10]),
        "spearman": _mean(spearman),
        "ndcg_at_5": _mean(ndcg),
        "mean_rank_error": _mean(rank_error),
    }


def selection_gate(
    candidate: dict[str, float | None], baseline: dict[str, float | None], rule: dict[str, float | None],
    fold_differences: list[float],
) -> tuple[str, str, int]:
    ndcg = candidate.get("ndcg_at_5")
    p5 = candidate.get("precision_at_5")
    reference_ndcg = max(float(baseline.get("ndcg_at_5") or 0), float(rule.get("ndcg_at_5") or 0))
    reference_p5 = max(float(baseline.get("precision_at_5") or 0), float(rule.get("precision_at_5") or 0))
    improving = sum(value > 0 for value in fold_differences)
    majority = bool(fold_differences) and improving >= math.ceil(len(fold_differences) / 2)
    positives = [value for value in fold_differences if value > 0]
    not_one_fold = len(positives) >= 2 and (max(positives) / sum(positives) <= .75 if sum(positives) else False)
    gate_a = ndcg is not None and p5 is not None and ndcg >= reference_ndcg + .02 and p5 >= reference_p5 - .02
    gate_b = ndcg is not None and p5 is not None and p5 >= reference_p5 + .05 and ndcg >= reference_ndcg
    passed = (gate_a or gate_b) and majority and not_one_fold
    reason = (
        f"{'PASS' if passed else 'FAIL'}: NDCG@5={ndcg if ndcg is not None else 'N/A'}, "
        f"P@5={p5 if p5 is not None else 'N/A'}, 개선 fold={improving}/{len(fold_differences)}"
    )
    return ("PASS" if passed else "FAIL", reason, improving)


class MarketThemeReturnRankMLService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _matrix(rows: list[ThemeFeatureRow]) -> np.ndarray:
        return np.asarray([[np.nan if row.values.get(name) is None else float(row.values[name]) for name in FEATURE_NAMES_V2] for row in rows])

    @staticmethod
    def _ridge() -> Pipeline:
        return Pipeline([("imputer", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)), ("scaler", StandardScaler()), ("model", Ridge(alpha=10.0))])

    @staticmethod
    def _hgbr() -> Pipeline:
        return Pipeline([("imputer", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)), ("model", HistGradientBoostingRegressor(max_iter=200, learning_rate=.05, max_depth=3, l2_regularization=1.0, random_state=42))])

    @staticmethod
    def _logistic() -> Pipeline:
        return Pipeline([("imputer", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)), ("scaler", StandardScaler()), ("model", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42))])

    @staticmethod
    def _hgbc() -> Pipeline:
        return Pipeline([("imputer", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)), ("model", HistGradientBoostingClassifier(max_iter=200, learning_rate=.05, max_depth=3, l2_regularization=1.0, random_state=42))])

    @staticmethod
    def _folds(rows: list[ThemeFeatureRow]) -> list[tuple[set[str], set[str]]]:
        dates = sorted({str(row.target_date) for row in rows if row.target_date})
        validation_size = max(10, min(20, max(10, (len(dates) - MIN_TRAIN_DATES) // 5)))
        return [(set(dates[:start]), set(dates[start:start + validation_size])) for start in range(MIN_TRAIN_DATES, len(dates), validation_size) if dates[start:start + validation_size]]

    def _version(self, model_type: str) -> str:
        prefix = f"ML-{model_type}-V1-{datetime.now().strftime('%Y%m%d')}"
        count = int(self.db.execute(text("SELECT COUNT(*) FROM market_theme_return_prediction_models WHERE model_version LIKE :prefix"), {"prefix": f"{prefix}-%"}).scalar() or 0)
        return f"{prefix}-{count + 1:02d}"

    def train_rank_candidates(self) -> MarketThemeReturnMLTrainResponse:
        dataset = MarketThemeReturnFeatureService(self.db).build_dataset(min_coverage=.70)
        rows = dataset.rows
        base_dates = sorted({row.base_date for row in rows})
        common = dict(feature_version=FEATURE_VERSION_V2, train_start_date=base_dates[0] if base_dates else None,
            train_end_date=base_dates[-1] if base_dates else None, distinct_base_dates=len(base_dates), train_row_count=len(rows),
            theme_count=len({row.theme_id for row in rows}), excluded_missing_label=dataset.excluded_missing_label,
            excluded_low_coverage=dataset.excluded_low_coverage, metric_version=METRIC_VERSION)
        if len(base_dates) < MIN_TRAIN_DATES or len(rows) < MIN_TRAIN_ROWS:
            return MarketThemeReturnMLTrainResponse(status="INSUFFICIENT_DATA", message="학습 데이터가 부족합니다.", **common)
        rank_labels = rank_percentiles(rows)
        top5 = top_k_labels(rows, 5)
        _ = top_percent_labels(rows)
        folds = self._folds(rows)
        names = ("RAW-RIDGE", "RAW-HGBR", "RESIDUAL-RIDGE", "RESIDUAL-HGBR", "RANK-RIDGE", "RANK-HGBR", "TOP5-LOGISTIC", "TOP5-HGBC")
        scores: dict[str, list[float]] = {name: [] for name in names}
        returns: dict[str, list[float] | None] = {name: [] if name.startswith(("RAW", "RESIDUAL")) else None for name in names}
        validation_rows: list[ThemeFeatureRow] = []
        fold_differences: dict[str, list[float]] = defaultdict(list)
        baseline_all: list[float] = []
        rule_all: list[float] = []
        for train_dates, validation_dates in folds:
            train = [row for row in rows if row.target_date in train_dates]
            validation = [row for row in rows if row.target_date in validation_dates]
            x_train, x_validation = self._matrix(train), self._matrix(validation)
            y_raw = np.asarray([float(row.label) for row in train])
            y_residual = np.asarray([float(row.label) - float(row.values["base_change_rate"]) for row in train])
            y_rank = np.asarray([rank_labels[(str(row.target_date), row.theme_id)] for row in train])
            y_top5 = np.asarray([top5[(str(row.target_date), row.theme_id)] for row in train])
            estimators = {
                "RAW-RIDGE": (self._ridge(), y_raw), "RAW-HGBR": (self._hgbr(), y_raw),
                "RESIDUAL-RIDGE": (self._ridge(), y_residual), "RESIDUAL-HGBR": (self._hgbr(), y_residual),
                "RANK-RIDGE": (self._ridge(), y_rank), "RANK-HGBR": (self._hgbr(), y_rank),
                "TOP5-LOGISTIC": (self._logistic(), y_top5), "TOP5-HGBC": (self._hgbc(), y_top5),
            }
            fold_scores: dict[str, list[float]] = {}
            fold_returns: dict[str, list[float] | None] = {}
            for name, (estimator, target) in estimators.items():
                if name.startswith("TOP5") and len(np.unique(target)) < 2:
                    prediction = np.full(len(validation), float(target[0]))
                else:
                    estimator.fit(x_train, target)
                    prediction = estimator.predict_proba(x_validation)[:, 1] if name.startswith("TOP5") else estimator.predict(x_validation)
                values = [float(value) for value in prediction]
                predicted_return = None
                if name.startswith("RAW"):
                    predicted_return = values
                elif name.startswith("RESIDUAL"):
                    predicted_return = [float(row.values["base_change_rate"]) + value for row, value in zip(validation, values)]
                score_values = predicted_return if predicted_return is not None else values
                scores[name].extend(score_values)
                if returns[name] is not None:
                    returns[name].extend(predicted_return or [])
                fold_scores[name], fold_returns[name] = score_values, predicted_return
            baseline = [float(row.values["base_change_rate"]) for row in validation]
            rule = [float(row.rule_prediction if row.rule_prediction is not None else row.values["base_change_rate"]) for row in validation]
            baseline_metric = evaluate_rank_predictions(validation, baseline, baseline)
            rule_metric = evaluate_rank_predictions(validation, rule, rule)
            reference = max(float(baseline_metric["ndcg_at_5"] or 0), float(rule_metric["ndcg_at_5"] or 0))
            for name in names:
                metric = evaluate_rank_predictions(validation, fold_scores[name], fold_returns[name])
                fold_differences[name].append(float(metric["ndcg_at_5"] or 0) - reference)
            validation_rows.extend(validation)
            baseline_all.extend(baseline)
            rule_all.extend(rule)
        if not validation_rows:
            return MarketThemeReturnMLTrainResponse(status="INSUFFICIENT_DATA", message="검증 fold를 만들 수 없습니다.", **common)
        # Shadow-only ensembles use validation predictions; no live or future values tune these fixed candidates.
        rank_source = "RANK-RIDGE" if (evaluate_rank_predictions(validation_rows, scores["RANK-RIDGE"])["ndcg_at_5"] or 0) >= (evaluate_rank_predictions(validation_rows, scores["RANK-HGBR"])["ndcg_at_5"] or 0) else "RANK-HGBR"
        top_source = "TOP5-LOGISTIC" if (evaluate_rank_predictions(validation_rows, scores["TOP5-LOGISTIC"])["ndcg_at_5"] or 0) >= (evaluate_rank_predictions(validation_rows, scores["TOP5-HGBC"])["ndcg_at_5"] or 0) else "TOP5-HGBC"
        residual_source = "RESIDUAL-RIDGE" if (evaluate_rank_predictions(validation_rows, scores["RESIDUAL-RIDGE"])["ndcg_at_5"] or 0) >= (evaluate_rank_predictions(validation_rows, scores["RESIDUAL-HGBR"])["ndcg_at_5"] or 0) else "RESIDUAL-HGBR"
        def normalize_by_date(values: list[float]) -> list[float]:
            output: list[float] = []
            offset = 0
            for target_date in sorted({str(row.target_date) for row in validation_rows}):
                count = sum(row.target_date == target_date for row in validation_rows)
                group = values[offset:offset + count]
                order = sorted(range(count), key=lambda index: (group[index], validation_rows[offset + index].theme_id))
                ranks = {index: rank for rank, index in enumerate(order)}
                output.extend([1.0 if count == 1 else ranks[index] / (count - 1) for index in range(count)])
                offset += count
            return output
        residual_normalized = normalize_by_date(scores[residual_source])
        ensemble_a = [.5 * rank + .5 * top for rank, top in zip(scores[rank_source], scores[top_source])]
        ensemble_b = [.4 * rank + .4 * top + .2 * residual for rank, top, residual in zip(scores[rank_source], scores[top_source], residual_normalized)]
        ensemble_a_metric = evaluate_rank_predictions(validation_rows, ensemble_a)
        ensemble_b_metric = evaluate_rank_predictions(validation_rows, ensemble_b)
        ensemble_weights = (.5, .5, 0.0) if (ensemble_a_metric["ndcg_at_5"] or 0) >= (ensemble_b_metric["ndcg_at_5"] or 0) else (.4, .4, .2)
        scores["RANK-ENSEMBLE"] = ensemble_a if ensemble_weights[2] == 0 else ensemble_b
        returns["RANK-ENSEMBLE"] = None
        names = names + ("RANK-ENSEMBLE",)
        baseline_metrics = evaluate_rank_predictions(validation_rows, baseline_all, baseline_all)
        rule_metrics = evaluate_rank_predictions(validation_rows, rule_all, rule_all)
        metrics = {name: evaluate_rank_predictions(validation_rows, scores[name], returns[name]) for name in names}
        # Ensemble fold stability is derived from component fold direction conservatively.
        fold_differences["RANK-ENSEMBLE"] = [min(a, b) for a, b in zip(fold_differences[rank_source], fold_differences[top_source])]
        gates = {name: selection_gate(metrics[name], baseline_metrics, rule_metrics, fold_differences[name]) for name in names}
        x_all = self._matrix(rows)
        label_sets = {
            "RAW": np.asarray([float(row.label) for row in rows]),
            "RESIDUAL": np.asarray([float(row.label) - float(row.values["base_change_rate"]) for row in rows]),
            "RANK": np.asarray([rank_labels[(str(row.target_date), row.theme_id)] for row in rows]),
            "TOP5": np.asarray([top5[(str(row.target_date), row.theme_id)] for row in rows]),
        }
        fitted: dict[str, Any] = {}
        factories: dict[str, Callable[[], Pipeline]] = {"RIDGE": self._ridge, "HGBR": self._hgbr, "LOGISTIC": self._logistic, "HGBC": self._hgbc}
        for name in names[:-1]:
            target_prefix, algorithm = name.split("-", 1)
            estimator = factories[algorithm]()
            estimator.fit(x_all, label_sets[target_prefix])
            fitted[name] = estimator
        timestamp = now_kst()
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        candidate_results: list[dict[str, Any]] = []
        try:
            for name in names:
                target_type = "RANK_ENSEMBLE" if name == "RANK-ENSEMBLE" else {"RAW": "RAW_RETURN", "RESIDUAL": "RESIDUAL_RETURN", "RANK": "RANK_PERCENTILE", "TOP5": "TOP5_CLASSIFICATION"}[name.split("-")[0]]
                model_version = self._version(name)
                artifact_path = ARTIFACT_DIR / f"{model_version.lower()}.joblib"
                artifact: dict[str, Any] = {"model_version": model_version, "model_type": name, "target_type": target_type,
                    "feature_version": FEATURE_VERSION_V2, "feature_names": FEATURE_NAMES_V2}
                if name == "RANK-ENSEMBLE":
                    artifact.update({"rank_model": fitted[rank_source], "top5_model": fitted[top_source], "residual_model": fitted[residual_source],
                        "rank_source": rank_source, "top5_source": top_source, "residual_source": residual_source, "weights": ensemble_weights})
                else:
                    artifact["model"] = fitted[name]
                joblib.dump(artifact, artifact_path)
                gate_status, gate_reason, improving_count = gates[name]
                metric = metrics[name]
                self.db.execute(text("""
                    INSERT INTO market_theme_return_prediction_models
                    (model_version,model_type,feature_version,status,target_type,parent_model_version,selection_gate_status,
                     selection_reason,trained_at,train_start_date,train_end_date,distinct_train_dates,train_row_count,
                     validation_fold_count,validation_improving_fold_count,metric_version,validation_mae,validation_rmse,
                     validation_mean_signed_gap,validation_direction_accuracy,validation_precision_at_3,validation_precision_at_5,
                     validation_precision_at_10,validation_spearman,validation_ndcg_at_5,validation_mean_rank_error,
                     rule_validation_mae,rule_validation_precision_at_5,rule_validation_ndcg_at_5,baseline_validation_mae,
                     baseline_validation_precision_at_5,baseline_validation_ndcg_at_5,artifact_path,sklearn_version,created_at,updated_at)
                    VALUES (:version,:model_type,:feature,'EXPERIMENTAL',:target_type,NULL,:gate,:reason,:now,:start,:end,:dates,:rows,
                     :folds,:improving,:metric_version,:mae,:rmse,:signed,:direction,:p3,:p5,:p10,:spearman,:ndcg,:rank_error,
                     :rule_mae,:rule_p5,:rule_ndcg,:baseline_mae,:baseline_p5,:baseline_ndcg,:artifact,:sklearn,:now,:now)
                """), {"version": model_version, "model_type": name, "feature": FEATURE_VERSION_V2, "target_type": target_type,
                    "gate": gate_status, "reason": gate_reason, "now": timestamp, "start": base_dates[0], "end": base_dates[-1],
                    "dates": len(base_dates), "rows": len(rows), "folds": len(folds), "improving": improving_count,
                    "metric_version": METRIC_VERSION, "mae": metric["mae"], "rmse": metric["rmse"], "signed": metric["mean_signed_gap"],
                    "direction": metric["direction_accuracy"], "p3": metric["precision_at_3"], "p5": metric["precision_at_5"],
                    "p10": metric["precision_at_10"], "spearman": metric["spearman"], "ndcg": metric["ndcg_at_5"],
                    "rank_error": metric["mean_rank_error"], "rule_mae": rule_metrics["mae"], "rule_p5": rule_metrics["precision_at_5"],
                    "rule_ndcg": rule_metrics["ndcg_at_5"], "baseline_mae": baseline_metrics["mae"],
                    "baseline_p5": baseline_metrics["precision_at_5"], "baseline_ndcg": baseline_metrics["ndcg_at_5"],
                    "artifact": str(artifact_path), "sklearn": sklearn.__version__})
                candidate_results.append({"model_type": name, "model_version": model_version, "target_type": target_type,
                    "selection_gate_status": gate_status, "selection_reason": gate_reason, "improving_fold_count": improving_count,
                    "validation_fold_count": len(folds), "metrics": metric})
            self.db.commit()
        except Exception:
            self.db.rollback()
            for item in candidate_results:
                (ARTIFACT_DIR / f"{item['model_version'].lower()}.joblib").unlink(missing_ok=True)
            raise
        passed = [item for item in candidate_results if item["selection_gate_status"] == "PASS"]
        proposed = max(passed, key=lambda item: (item["metrics"]["ndcg_at_5"] or -math.inf, item["metrics"]["precision_at_5"] or -math.inf), default=None)
        return MarketThemeReturnMLTrainResponse(status="COMPLETED", message="Phase3 순위 목적 후보 학습과 Gate 평가가 완료되었습니다.",
            **common, validation_fold_count=len(folds), candidates=candidate_results, baseline_metrics=baseline_metrics,
            rule_metrics=rule_metrics, selected_model_type=proposed["model_type"] if proposed else None,
            model_version=proposed["model_version"] if proposed else None, proposed_shadow_model_version=proposed["model_version"] if proposed else None,
            sklearn_version=sklearn.__version__)

    def select_shadow(self, model_version: str) -> MarketThemeReturnMLStatusResponse:
        model = self.db.execute(text("SELECT * FROM market_theme_return_prediction_models WHERE model_version=:version"), {"version": model_version}).mappings().first()
        if not model:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="모델을 찾을 수 없습니다.")
        if model["selection_gate_status"] != "PASS":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Gate PASS 모델만 Shadow로 선택할 수 있습니다.")
        if model["feature_version"] not in {FEATURE_VERSION_V2} or not Path(str(model["artifact_path"])).is_file():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="모델 artifact 또는 feature version이 유효하지 않습니다.")
        timestamp = now_kst()
        self.db.execute(text("UPDATE market_theme_return_prediction_models SET status='RETIRED',updated_at=:now WHERE status='SHADOW'"), {"now": timestamp})
        self.db.execute(text("UPDATE market_theme_return_prediction_models SET status='SHADOW',shadow_selected_at=:now,updated_at=:now WHERE model_version=:version"), {"now": timestamp, "version": model_version})
        self.db.commit()
        return self.status()

    def _window(self, model_version: str, limit: int | None) -> MarketThemeReturnMLPerformanceWindow:
        limit_clause = "LIMIT :limit" if limit else ""
        rows = self.db.execute(text(f"""
            SELECT r.return_mae rule_mae,r.precision_at_5 rule_p5,r.ndcg_at_5 rule_ndcg,r.mean_rank_error rule_rank,
                   m.return_mae ml_mae,m.precision_at_5 ml_p5,m.ndcg_at_5 ml_ndcg,m.mean_rank_error ml_rank
              FROM market_theme_return_prediction_method_metrics r
              JOIN market_theme_return_prediction_method_metrics m ON m.run_id=r.run_id AND m.prediction_method='ML' AND m.model_version=:version
             WHERE r.prediction_method='RULE' ORDER BY r.run_id DESC {limit_clause}
        """), {"version": model_version, "limit": limit}).mappings().all()
        count = len(rows)
        def metrics(prefix: str) -> dict[str, float | None]:
            return {"mae": _mean([float(row[f"{prefix}_mae"]) for row in rows if row[f"{prefix}_mae"] is not None]),
                "precision_at_5": _mean([float(row[f"{prefix}_p5"]) for row in rows if row[f"{prefix}_p5"] is not None]),
                "ndcg_at_5": _mean([float(row[f"{prefix}_ndcg"]) for row in rows if row[f"{prefix}_ndcg"] is not None]),
                "mean_rank_error": _mean([float(row[f"{prefix}_rank"]) for row in rows if row[f"{prefix}_rank"] is not None])}
        rule, ml = metrics("rule"), metrics("ml")
        difference = lambda key: None if rule[key] is None or ml[key] is None else float(ml[key]) - float(rule[key])
        return MarketThemeReturnMLPerformanceWindow(sample_size=count, sufficient=count >= (limit or 1), rule_metrics=rule, ml_metrics=ml,
            ndcg_difference=difference("ndcg_at_5"), precision_at_5_difference=difference("precision_at_5"),
            mean_rank_error_difference=difference("mean_rank_error"))

    def status(self) -> MarketThemeReturnMLStatusResponse:
        model = self.db.execute(text("SELECT * FROM market_theme_return_prediction_models WHERE status='SHADOW' ORDER BY trained_at DESC,id DESC LIMIT 1")).mappings().first()
        if not model:
            return MarketThemeReturnMLStatusResponse(status="UNAVAILABLE", available=False)
        version = str(model["model_version"])
        recent5, recent20, all_common = self._window(version, 5), self._window(version, 20), self._window(version, None)
        count = all_common.sample_size
        readiness = "NOT_READY"
        if count >= MIN_LIVE_REVIEW_RUNS:
            rm, mm = recent20.rule_metrics, recent20.ml_metrics
            daily = self.db.execute(text("""
                SELECT m.ndcg_at_5-r.ndcg_at_5 AS improvement
                  FROM market_theme_return_prediction_method_metrics r
                  JOIN market_theme_return_prediction_method_metrics m
                    ON m.run_id=r.run_id AND m.prediction_method='ML' AND m.model_version=:version
                 WHERE r.prediction_method='RULE' ORDER BY r.run_id DESC LIMIT 20
            """), {"version": version}).scalars().all()
            positive = [float(value) for value in daily if value is not None and float(value) > 0]
            stable_dates = len(positive) >= math.ceil(len(daily) / 2)
            not_concentrated = len(positive) >= 2 and sum(sorted(positive, reverse=True)[:3]) <= sum(positive) * .70
            improved = bool(rm and mm and mm.ndcg_at_5 is not None and rm.ndcg_at_5 is not None and mm.ndcg_at_5 > rm.ndcg_at_5
                and mm.precision_at_5 is not None and rm.precision_at_5 is not None and mm.precision_at_5 >= rm.precision_at_5
                and mm.mean_rank_error is not None and rm.mean_rank_error is not None and mm.mean_rank_error <= rm.mean_rank_error
                and stable_dates and not_concentrated)
            readiness = "ELIGIBLE_FOR_REVIEW" if improved else "OBSERVE"
        live_ndcg = recent20.ml_metrics.ndcg_at_5 if recent20.sufficient and recent20.ml_metrics else None
        validation_ndcg = model["validation_ndcg_at_5"]
        drop = None if live_ndcg is None or validation_ndcg is None else float(validation_ndcg) - float(live_ndcg)
        live_mae = recent20.ml_metrics.mae if recent20.sufficient and recent20.ml_metrics else None
        validation_mae = model["validation_mae"]
        mae_ratio = None if live_mae is None or validation_mae in (None, 0) else (float(live_mae) - float(validation_mae)) / float(validation_mae)
        drift = "WATCH" if drop is None and mae_ratio is None else (
            "DEGRADED" if (drop is not None and drop >= DRIFT_NDCG_DEGRADED) or (mae_ratio is not None and mae_ratio >= DRIFT_MAE_DEGRADED_RATIO)
            else "WATCH" if (drop is not None and drop >= DRIFT_NDCG_WATCH) or (mae_ratio is not None and mae_ratio >= DRIFT_MAE_WATCH_RATIO)
            else "STABLE"
        )
        advice_code = "ML_SAMPLE_INSUFFICIENT" if readiness == "NOT_READY" else "ML_READY_FOR_REVIEW" if readiness == "ELIGIBLE_FOR_REVIEW" else "ML_IMPROVING" if (recent20.ndcg_difference or 0) > 0 else "ML_RANK_WEAK"
        advice = {"ML_SAMPLE_INSUFFICIENT": "실전 공통 검증 데이터가 부족합니다.", "ML_READY_FOR_REVIEW": "ML이 검토 Gate를 충족했습니다. 자동 승격되지는 않습니다.",
            "ML_IMPROVING": "ML의 상위 테마 순위가 RULE보다 개선되는 경향이 있습니다.", "ML_RANK_WEAK": "ML 순위 성능이 아직 RULE보다 안정적으로 높지 않습니다."}[advice_code]
        metrics = {"mae": model["validation_mae"], "rmse": model["validation_rmse"], "mean_signed_gap": model["validation_mean_signed_gap"],
            "direction_accuracy": model["validation_direction_accuracy"], "precision_at_3": model["validation_precision_at_3"],
            "precision_at_5": model["validation_precision_at_5"], "precision_at_10": model["validation_precision_at_10"],
            "spearman": model["validation_spearman"], "ndcg_at_5": model["validation_ndcg_at_5"], "mean_rank_error": model["validation_mean_rank_error"]}
        return MarketThemeReturnMLStatusResponse(status=str(model["status"]), available=True, model_version=version,
            model_type=str(model["model_type"]), target_type=str(model["target_type"]), feature_version=str(model["feature_version"]),
            trained_at=str(model["trained_at"]), train_start_date=str(model["train_start_date"]), train_end_date=str(model["train_end_date"]),
            distinct_train_dates=int(model["distinct_train_dates"]), train_row_count=int(model["train_row_count"]),
            validation_fold_count=int(model["validation_fold_count"]), validation_metrics=metrics,
            rule_metrics={"mae": model["rule_validation_mae"], "precision_at_5": model["rule_validation_precision_at_5"], "ndcg_at_5": model["rule_validation_ndcg_at_5"]},
            baseline_metrics={"mae": model["baseline_validation_mae"], "precision_at_5": model["baseline_validation_precision_at_5"], "ndcg_at_5": model["baseline_validation_ndcg_at_5"]},
            artifact_path=str(model["artifact_path"]), selection_gate_status=str(model["selection_gate_status"]), selection_reason=model["selection_reason"],
            common_evaluated_runs=count, readiness=readiness, promotion_readiness=readiness, drift_status=drift,
            recent_5=recent5, recent_20=recent20, all_common=all_common, remaining_runs_for_review=max(0, MIN_LIVE_REVIEW_RUNS-count),
            advice_code=advice_code, advice_message=advice)
