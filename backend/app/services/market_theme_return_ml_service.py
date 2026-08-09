from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import math
import os
from pathlib import Path
from threading import Lock
from typing import Any

import joblib
import numpy as np
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")
import sklearn
from fastapi import HTTPException, status
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.schemas.market_theme_return_prediction_schema import (
    MarketThemeReturnMLStatusResponse,
    MarketThemeReturnMLTrainResponse,
)
from backend.app.services.market_theme_return_feature_service import (
    FEATURE_NAMES,
    FEATURE_VERSION,
    FEATURE_NAMES_V2,
    FEATURE_VERSION_V2,
    MarketThemeReturnFeatureService,
    ThemeFeatureRow,
)
from backend.app.services.market_theme_return_rank_ml_service import METRIC_VERSION, evaluate_rank_predictions


MIN_TRAIN_DATES = 40
NORMAL_SHADOW_DATES = 80
MIN_TRAIN_ROWS = 500
MODEL_ARTIFACT_DIR = Path(__file__).resolve().parents[2] / "model_artifacts" / "theme_return_prediction"

_MODEL_CACHE: dict[str, tuple[str, dict[str, Any]]] = {}
_MODEL_CACHE_LOCK = Lock()


def _safe_mean(values: list[float]) -> float | None:
    return float(np.mean(values)) if values else None


def _precision(predicted: list[int], actual: list[int], k: int) -> float | None:
    size = min(k, len(predicted), len(actual))
    return None if size == 0 else len(set(predicted[:size]) & set(actual[:size])) / size


def _ndcg(predicted: list[int], actual: list[int], k: int = 5) -> float | None:
    if not predicted or not actual:
        return None
    actual_rank = {theme_id: rank for rank, theme_id in enumerate(actual, 1)}
    relevance = {theme_id: max(0, len(actual) - rank + 1) for theme_id, rank in actual_rank.items()}
    dcg = sum((2 ** relevance.get(theme_id, 0) - 1) / math.log2(index + 2) for index, theme_id in enumerate(predicted[:k]))
    ideal = sum((2 ** relevance[theme_id] - 1) / math.log2(index + 2) for index, theme_id in enumerate(actual[:k]))
    return dcg / ideal if ideal else None


def evaluate_predictions(rows: list[ThemeFeatureRow], predictions: list[float]) -> dict[str, float | None]:
    if not rows:
        return {key: None for key in ("mae", "rmse", "mean_signed_gap", "direction_accuracy", "precision_at_3",
            "precision_at_5", "precision_at_10", "spearman", "ndcg_at_5", "mean_rank_error")}
    errors = [float(row.label) - float(prediction) for row, prediction in zip(rows, predictions) if row.label is not None]
    by_date: dict[str, list[tuple[ThemeFeatureRow, float]]] = defaultdict(list)
    for row, prediction in zip(rows, predictions):
        if row.label is not None and row.target_date:
            by_date[row.target_date].append((row, float(prediction)))
    precision3: list[float] = []
    precision5: list[float] = []
    precision10: list[float] = []
    spearman_values: list[float] = []
    ndcg_values: list[float] = []
    rank_errors: list[float] = []
    for pairs in by_date.values():
        predicted_order = [row.theme_id for row, _ in sorted(pairs, key=lambda pair: (-pair[1], pair[0].theme_id))]
        actual_order = [row.theme_id for row, _ in sorted(pairs, key=lambda pair: (-float(pair[0].label), pair[0].theme_id))]
        p_rank = {theme_id: rank for rank, theme_id in enumerate(predicted_order, 1)}
        a_rank = {theme_id: rank for rank, theme_id in enumerate(actual_order, 1)}
        for k, target in ((3, precision3), (5, precision5), (10, precision10)):
            value = _precision(predicted_order, actual_order, k)
            if value is not None:
                target.append(value)
        n = len(predicted_order)
        if n > 1:
            d2 = sum((p_rank[theme_id] - a_rank[theme_id]) ** 2 for theme_id in predicted_order)
            spearman_values.append(1 - 6 * d2 / (n * (n * n - 1)))
        ndcg_value = _ndcg(predicted_order, actual_order)
        if ndcg_value is not None:
            ndcg_values.append(ndcg_value)
        rank_errors.extend(abs(p_rank[theme_id] - a_rank[theme_id]) for theme_id in predicted_order)
    return {
        "mae": _safe_mean([abs(value) for value in errors]),
        "rmse": math.sqrt(float(np.mean([value * value for value in errors]))) if errors else None,
        "mean_signed_gap": _safe_mean(errors),
        "direction_accuracy": _safe_mean([float((abs(float(row.label)) <= .5 and abs(float(prediction)) <= .5) or ((float(row.label) > .5) == (float(prediction) > .5) and (float(row.label) < -.5) == (float(prediction) < -.5))) for row, prediction in zip(rows, predictions) if row.label is not None]),
        "precision_at_3": _safe_mean(precision3), "precision_at_5": _safe_mean(precision5),
        "precision_at_10": _safe_mean(precision10), "spearman": _safe_mean(spearman_values),
        "ndcg_at_5": _safe_mean(ndcg_values), "mean_rank_error": _safe_mean(rank_errors),
    }


class MarketThemeReturnMLService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _ensure_phase3_compatibility_columns(self) -> None:
        item_columns = {str(row[1]) for row in self.db.execute(text("PRAGMA table_info(market_theme_return_prediction_items)")).all()}
        if "top5_probability" not in item_columns:
            self.db.execute(text("ALTER TABLE market_theme_return_prediction_items ADD COLUMN top5_probability REAL"))
        metric_columns = {str(row[1]) for row in self.db.execute(text("PRAGMA table_info(market_theme_return_prediction_method_metrics)")).all()}
        if metric_columns and "metric_version" not in metric_columns:
            self.db.execute(text("ALTER TABLE market_theme_return_prediction_method_metrics ADD COLUMN metric_version TEXT NOT NULL DEFAULT 'THEME_RETURN_METRIC_V1'"))

    @staticmethod
    def _matrix(rows: list[ThemeFeatureRow], feature_names: tuple[str, ...] = FEATURE_NAMES) -> np.ndarray:
        return np.asarray([[np.nan if row.values.get(name) is None else float(row.values[name]) for name in feature_names] for row in rows], dtype=float)

    @staticmethod
    def _ridge() -> Pipeline:
        return Pipeline([
            ("imputer", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)),
            ("scaler", StandardScaler()),
            ("model", Ridge(alpha=10.0)),
        ])

    @staticmethod
    def _boosting() -> Pipeline:
        return Pipeline([
            ("imputer", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)),
            ("model", HistGradientBoostingRegressor(max_iter=200, learning_rate=.05, max_depth=3, l2_regularization=1.0, random_state=42)),
        ])

    @staticmethod
    def _selection_key(item: tuple[str, dict[str, float | None]]) -> tuple[float, float, float, int]:
        name, metrics = item
        return (
            -(metrics.get("ndcg_at_5") if metrics.get("ndcg_at_5") is not None else -math.inf),
            -(metrics.get("precision_at_5") if metrics.get("precision_at_5") is not None else -math.inf),
            metrics.get("mae") if metrics.get("mae") is not None else math.inf,
            0 if name == "RIDGE" else 1,
        )

    def _version(self, model_type: str) -> str:
        prefix = f"ML-{model_type}-V1-{datetime.now().strftime('%Y%m%d')}"
        count = int(self.db.execute(text("SELECT COUNT(*) FROM market_theme_return_prediction_models WHERE model_version LIKE :prefix"), {"prefix": f"{prefix}-%"}).scalar() or 0)
        return f"{prefix}-{count + 1:02d}"

    def train_shadow(self) -> MarketThemeReturnMLTrainResponse:
        dataset = MarketThemeReturnFeatureService(self.db).build_dataset(min_coverage=.70)
        rows = dataset.rows
        base_dates = sorted({row.base_date for row in rows})
        theme_count = len({row.theme_id for row in rows})
        common = {
            "status": "INSUFFICIENT_DATA", "message": "학습 데이터가 부족합니다.", "feature_version": FEATURE_VERSION,
            "train_start_date": base_dates[0] if base_dates else None, "train_end_date": base_dates[-1] if base_dates else None,
            "distinct_base_dates": len(base_dates), "train_row_count": len(rows), "theme_count": theme_count,
            "excluded_missing_label": dataset.excluded_missing_label, "excluded_low_coverage": dataset.excluded_low_coverage,
        }
        if len(base_dates) < MIN_TRAIN_DATES or len(rows) < MIN_TRAIN_ROWS:
            return MarketThemeReturnMLTrainResponse(**common)
        target_dates = sorted({str(row.target_date) for row in rows if row.target_date})
        validation_size = max(10, min(20, max(10, (len(target_dates) - MIN_TRAIN_DATES) // 5)))
        folds: list[tuple[set[str], set[str]]] = []
        for start in range(MIN_TRAIN_DATES, len(target_dates), validation_size):
            validation = target_dates[start : start + validation_size]
            if not validation:
                break
            folds.append((set(target_dates[:start]), set(validation)))
        candidate_predictions: dict[str, list[float]] = {"RIDGE": [], "HGBR": []}
        validation_rows: list[ThemeFeatureRow] = []
        baseline_predictions: list[float] = []
        rule_predictions: list[float] = []
        for train_dates, validation_dates in folds:
            train_rows = [row for row in rows if row.target_date in train_dates]
            fold_rows = [row for row in rows if row.target_date in validation_dates]
            if not train_rows or not fold_rows:
                continue
            x_train, y_train = self._matrix(train_rows), np.asarray([float(row.label) for row in train_rows])
            x_validation = self._matrix(fold_rows)
            for name, estimator in (("RIDGE", self._ridge()), ("HGBR", self._boosting())):
                estimator.fit(x_train, y_train)
                candidate_predictions[name].extend(float(value) for value in estimator.predict(x_validation))
            validation_rows.extend(fold_rows)
            baseline_predictions.extend(float(row.values["base_change_rate"]) for row in fold_rows)
            rule_predictions.extend(float(row.rule_prediction if row.rule_prediction is not None else row.values["base_change_rate"]) for row in fold_rows)
        if not validation_rows:
            return MarketThemeReturnMLTrainResponse(**common)
        candidate_metrics = {name: evaluate_predictions(validation_rows, values) for name, values in candidate_predictions.items()}
        baseline_metrics = evaluate_predictions(validation_rows, baseline_predictions)
        rule_metrics = evaluate_predictions(validation_rows, rule_predictions)
        selected_type, selected_metrics = min(candidate_metrics.items(), key=self._selection_key)
        estimator = self._ridge() if selected_type == "RIDGE" else self._boosting()
        estimator.fit(self._matrix(rows), np.asarray([float(row.label) for row in rows]))
        model_version = self._version(selected_type)
        MODEL_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        artifact_path = MODEL_ARTIFACT_DIR / f"{model_version.lower()}.joblib"
        joblib.dump({"model": estimator, "model_version": model_version, "model_type": selected_type,
                     "feature_version": FEATURE_VERSION, "feature_names": FEATURE_NAMES}, artifact_path)
        timestamp = now_kst()
        model_status = "SHADOW" if len(base_dates) >= NORMAL_SHADOW_DATES else "EXPERIMENTAL"
        try:
            if model_status == "SHADOW":
                self.db.execute(text("UPDATE market_theme_return_prediction_models SET status='RETIRED',updated_at=:now WHERE status='SHADOW'"), {"now": timestamp})
            self.db.execute(text("""
                INSERT INTO market_theme_return_prediction_models
                (model_version,model_type,feature_version,status,trained_at,train_start_date,train_end_date,distinct_train_dates,
                 train_row_count,validation_fold_count,validation_mae,validation_rmse,validation_mean_signed_gap,
                 validation_direction_accuracy,validation_precision_at_3,validation_precision_at_5,validation_precision_at_10,
                 validation_spearman,validation_ndcg_at_5,validation_mean_rank_error,rule_validation_mae,
                 rule_validation_precision_at_5,rule_validation_ndcg_at_5,baseline_validation_mae,
                 baseline_validation_precision_at_5,baseline_validation_ndcg_at_5,artifact_path,sklearn_version,created_at,updated_at)
                VALUES (:model_version,:model_type,:feature_version,:status,:now,:start,:end,:dates,:rows,:folds,:mae,:rmse,
                 :signed,:direction,:p3,:p5,:p10,:spearman,:ndcg,:rank_error,:rule_mae,:rule_p5,:rule_ndcg,
                 :baseline_mae,:baseline_p5,:baseline_ndcg,:artifact,:sklearn,:now,:now)
            """), {"model_version": model_version, "model_type": selected_type, "feature_version": FEATURE_VERSION,
                "status": model_status, "now": timestamp, "start": base_dates[0], "end": base_dates[-1], "dates": len(base_dates),
                "rows": len(rows), "folds": len(folds), "mae": selected_metrics["mae"], "rmse": selected_metrics["rmse"],
                "signed": selected_metrics["mean_signed_gap"], "direction": selected_metrics["direction_accuracy"],
                "p3": selected_metrics["precision_at_3"], "p5": selected_metrics["precision_at_5"], "p10": selected_metrics["precision_at_10"],
                "spearman": selected_metrics["spearman"], "ndcg": selected_metrics["ndcg_at_5"], "rank_error": selected_metrics["mean_rank_error"],
                "rule_mae": rule_metrics["mae"], "rule_p5": rule_metrics["precision_at_5"], "rule_ndcg": rule_metrics["ndcg_at_5"],
                "baseline_mae": baseline_metrics["mae"], "baseline_p5": baseline_metrics["precision_at_5"],
                "baseline_ndcg": baseline_metrics["ndcg_at_5"], "artifact": str(artifact_path), "sklearn": sklearn.__version__})
            self.db.commit()
        except Exception:
            self.db.rollback()
            artifact_path.unlink(missing_ok=True)
            raise
        with _MODEL_CACHE_LOCK:
            _MODEL_CACHE.clear()
        return MarketThemeReturnMLTrainResponse(**{**common, "status": model_status, "message": "ML 그림자 모델 학습이 완료되었습니다."},
            validation_fold_count=len(folds), candidates=[{"model_type": name, "metrics": metrics} for name, metrics in candidate_metrics.items()],
            baseline_metrics=baseline_metrics, rule_metrics=rule_metrics, selected_model_type=selected_type,
            model_version=model_version, artifact_path=str(artifact_path), sklearn_version=sklearn.__version__)

    def _active_model(self) -> dict[str, Any] | None:
        row = self.db.execute(text("SELECT * FROM market_theme_return_prediction_models WHERE status='SHADOW' ORDER BY trained_at DESC,id DESC LIMIT 1")).mappings().first()
        return dict(row) if row else None

    @staticmethod
    def _load_artifact(model: dict[str, Any]) -> dict[str, Any]:
        version, path = str(model["model_version"]), str(model["artifact_path"])
        with _MODEL_CACHE_LOCK:
            cached = _MODEL_CACHE.get(version)
            if cached and cached[0] == path:
                return cached[1]
            artifact_path = Path(path)
            if not artifact_path.is_file():
                raise FileNotFoundError(f"ML artifact not found: {artifact_path}")
            artifact = joblib.load(artifact_path)
            supported = {FEATURE_VERSION: FEATURE_NAMES, FEATURE_VERSION_V2: FEATURE_NAMES_V2}
            if artifact.get("feature_version") not in supported or tuple(artifact.get("feature_names", ())) != supported[artifact["feature_version"]]:
                raise ValueError("ML feature version is incompatible")
            _MODEL_CACHE.clear()
            _MODEL_CACHE[version] = (path, artifact)
            return artifact

    def predict_shadow(self, target_date: str, *, require_model: bool = True):
        self._ensure_phase3_compatibility_columns()
        run = self.db.execute(text("SELECT * FROM market_theme_return_prediction_runs WHERE target_date=:target AND status<>'CANCELLED' ORDER BY id DESC LIMIT 1"), {"target": target_date}).mappings().first()
        if not run:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="해당 대상일의 공식 RULE 예측을 찾을 수 없습니다.")
        model = self._active_model()
        if not model:
            if require_model:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="활성 ML 그림자 모델이 없습니다.")
            return None
        try:
            artifact = self._load_artifact(model)
            rows = MarketThemeReturnFeatureService(self.db).build_for_date(str(run["data_cutoff_date"]), target_date, min_coverage=.70)
            if not rows:
                raise ValueError("ML 추론 가능한 테마 feature가 없습니다.")
            feature_names = tuple(artifact.get("feature_names", FEATURE_NAMES))
            matrix = self._matrix(rows, feature_names)
            target_type = str(artifact.get("target_type") or "RAW_RETURN")
            top5_probabilities: list[float | None] = [None] * len(rows)
            predicted_returns: list[float | None]
            if target_type == "RANK_ENSEMBLE":
                rank_scores = [float(value) for value in artifact["rank_model"].predict(matrix)]
                top_scores = [float(value) for value in artifact["top5_model"].predict_proba(matrix)[:, 1]]
                residual_returns = [float(row.values["base_change_rate"]) + float(value) for row, value in zip(rows, artifact["residual_model"].predict(matrix))]
                residual_order = sorted(range(len(rows)), key=lambda index: (residual_returns[index], rows[index].theme_id))
                residual_rank = {index: (1.0 if len(rows) == 1 else rank / (len(rows) - 1)) for rank, index in enumerate(residual_order)}
                weights = tuple(float(value) for value in artifact.get("weights", (.5, .5, 0)))
                predictions = [weights[0] * rank_scores[index] + weights[1] * top_scores[index] + weights[2] * residual_rank[index] for index in range(len(rows))]
                predicted_returns = [None] * len(rows)
                top5_probabilities = top_scores
            elif target_type == "TOP5_CLASSIFICATION":
                predictions = [float(value) for value in artifact["model"].predict_proba(matrix)[:, 1]]
                predicted_returns = [None] * len(rows)
                top5_probabilities = predictions
            elif target_type == "RANK_PERCENTILE":
                predictions = [float(value) for value in artifact["model"].predict(matrix)]
                predicted_returns = [None] * len(rows)
            elif target_type == "RESIDUAL_RETURN":
                predictions = [float(row.values["base_change_rate"]) + float(value) for row, value in zip(rows, artifact["model"].predict(matrix))]
                predicted_returns = list(predictions)
            else:
                predictions = [float(value) for value in artifact["model"].predict(matrix)]
                predicted_returns = list(predictions)
            order = sorted(range(len(rows)), key=lambda index: (-predictions[index], rows[index].theme_name, rows[index].theme_id))
            ranks = {index: rank for rank, index in enumerate(order, 1)}
            scores = {index: (100.0 if len(order) == 1 else (len(order) - rank) / (len(order) - 1) * 100) for rank, index in enumerate(order, 1)}
            timestamp = now_kst()
            self.db.execute(text("""
                INSERT INTO market_theme_return_prediction_items
                (run_id,theme_id,prediction_method,is_official,model_version,base_change_rate,predicted_change_rate,
                 prediction_score,top5_probability,predicted_rank,data_coverage_rate,penalty_score,evaluation_status,created_at,updated_at)
                VALUES (:run_id,:theme_id,'ML',0,:model_version,:base,:predicted,:score,:top5,:rank,:coverage,0,'NOT_EVALUATED',:now,:now)
                ON CONFLICT(run_id,theme_id,prediction_method) DO UPDATE SET model_version=excluded.model_version,
                 base_change_rate=excluded.base_change_rate,predicted_change_rate=excluded.predicted_change_rate,
                 prediction_score=excluded.prediction_score,top5_probability=excluded.top5_probability,predicted_rank=excluded.predicted_rank,
                 data_coverage_rate=excluded.data_coverage_rate,evaluation_status='NOT_EVALUATED',actual_change_rate=NULL,
                 actual_rank=NULL,signed_gap=NULL,absolute_gap=NULL,rank_gap=NULL,direction_hit=NULL,
                 baseline_absolute_error=NULL,prediction_effect=NULL,evaluated_at=NULL,updated_at=excluded.updated_at
            """), [{"run_id": run["id"], "theme_id": row.theme_id, "model_version": model["model_version"],
                     "base": row.values["base_change_rate"], "predicted": predicted_returns[index], "score": predictions[index],
                     "top5": top5_probabilities[index],
                     "rank": ranks[index], "coverage": row.values["data_coverage_rate"], "now": timestamp}
                    for index, row in enumerate(rows)])
            self.db.commit()
        except HTTPException:
            raise
        except Exception as exc:
            self.db.rollback()
            if require_model:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"ML 그림자 추론 실패: {exc}") from exc
            return None
        from backend.app.services.market_theme_return_prediction_service import MarketThemeReturnPredictionService
        return MarketThemeReturnPredictionService(self.db).get(target_date)

    def _upsert_method_metrics(self, run_id: int, method: str, model_version: str, metrics: dict[str, float | None], theme_count: int, timestamp: str) -> None:
        self._ensure_phase3_compatibility_columns()
        self.db.execute(text("""
            INSERT INTO market_theme_return_prediction_method_metrics
            (run_id,prediction_method,model_version,theme_count,evaluable_theme_count,return_mae,return_rmse,
             mean_signed_gap,mean_rank_error,top1_hit,precision_at_3,precision_at_5,precision_at_10,direction_accuracy,
             spearman_rank_correlation,ndcg_at_5,metric_version,evaluated_at,created_at,updated_at)
            VALUES (:run_id,:method,:version,:theme_count,:evaluable,:mae,:rmse,:signed,:rank_error,:top1,:p3,:p5,:p10,
             :direction,:spearman,:ndcg,:metric_version,:now,:now,:now)
            ON CONFLICT(run_id,prediction_method,model_version) DO UPDATE SET theme_count=excluded.theme_count,
             evaluable_theme_count=excluded.evaluable_theme_count,return_mae=excluded.return_mae,return_rmse=excluded.return_rmse,
             mean_signed_gap=excluded.mean_signed_gap,mean_rank_error=excluded.mean_rank_error,top1_hit=excluded.top1_hit,
             precision_at_3=excluded.precision_at_3,precision_at_5=excluded.precision_at_5,precision_at_10=excluded.precision_at_10,
             direction_accuracy=excluded.direction_accuracy,spearman_rank_correlation=excluded.spearman_rank_correlation,
             ndcg_at_5=excluded.ndcg_at_5,metric_version=excluded.metric_version,evaluated_at=excluded.evaluated_at,updated_at=excluded.updated_at
        """), {"run_id": run_id, "method": method, "version": model_version, "theme_count": theme_count,
                "evaluable": int(metrics.pop("evaluable")), "mae": metrics["mae"], "rmse": metrics["rmse"],
                "signed": metrics["mean_signed_gap"], "rank_error": metrics["mean_rank_error"], "top1": metrics.get("top1_hit"),
                "p3": metrics["precision_at_3"], "p5": metrics["precision_at_5"], "p10": metrics["precision_at_10"],
                "direction": metrics["direction_accuracy"], "spearman": metrics["spearman"], "ndcg": metrics["ndcg_at_5"],
                "metric_version": METRIC_VERSION, "now": timestamp})

    def validate_methods(self, target_date: str) -> None:
        run = self.db.execute(text("SELECT * FROM market_theme_return_prediction_runs WHERE target_date=:target AND status<>'CANCELLED' ORDER BY id DESC LIMIT 1"), {"target": target_date}).mappings().first()
        if not run:
            return
        actual_rows = self.db.execute(text("SELECT theme_id,avg_change_rate FROM market_theme_daily_returns WHERE return_date=:target AND avg_change_rate IS NOT NULL"), {"target": target_date}).mappings().all()
        if not actual_rows:
            return
        actual = {int(row["theme_id"]): float(row["avg_change_rate"]) for row in actual_rows}
        actual_order = [theme_id for theme_id, _ in sorted(actual.items(), key=lambda item: (-item[1], item[0]))]
        actual_rank = {theme_id: rank for rank, theme_id in enumerate(actual_order, 1)}
        items = [dict(row) for row in self.db.execute(text("SELECT * FROM market_theme_return_prediction_items WHERE run_id=:run_id"), {"run_id": run["id"]}).mappings().all()]
        timestamp = now_kst()
        for item in items:
            if item["prediction_method"] != "ML" or item["theme_id"] not in actual or item["predicted_rank"] is None:
                continue
            actual_value = actual[int(item["theme_id"])]
            predicted = None if item["predicted_change_rate"] is None else float(item["predicted_change_rate"])
            absolute = None if predicted is None else abs(actual_value - predicted)
            baseline = abs(actual_value - float(item["base_change_rate"])) if item["base_change_rate"] is not None else None
            self.db.execute(text("""UPDATE market_theme_return_prediction_items SET actual_change_rate=:actual,actual_rank=:actual_rank,
                signed_gap=:gap,absolute_gap=:absolute,rank_gap=:rank_gap,direction_hit=:direction,baseline_absolute_error=:baseline,
                prediction_effect=:effect,evaluation_status='COMPLETE',evaluated_at=:now,updated_at=:now WHERE id=:id"""),
                {"actual": actual_value, "actual_rank": actual_rank[int(item["theme_id"])], "gap": None if predicted is None else actual_value - predicted,
                 "absolute": absolute, "rank_gap": actual_rank[int(item["theme_id"])] - int(item["predicted_rank"]),
                 "direction": None if predicted is None else int((actual_value > .5) == (predicted > .5) and (actual_value < -.5) == (predicted < -.5)),
                 "baseline": baseline, "effect": baseline - absolute if baseline is not None and absolute is not None else None, "now": timestamp, "id": item["id"]})
        items = [dict(row) for row in self.db.execute(text("SELECT * FROM market_theme_return_prediction_items WHERE run_id=:run_id"), {"run_id": run["id"]}).mappings().all()]
        rule_ids = {int(item["theme_id"]) for item in items if item["prediction_method"] == "RULE" and item["theme_id"] in actual and item["predicted_rank"] is not None}
        ml_ids = {int(item["theme_id"]) for item in items if item["prediction_method"] == "ML" and item["theme_id"] in actual and item["predicted_rank"] is not None}
        common_ids = rule_ids & ml_ids if ml_ids else rule_ids
        for method in ("RULE", "ML"):
            method_items = [item for item in items if item["prediction_method"] == method and int(item["theme_id"]) in common_ids and item["predicted_rank"] is not None]
            rows = [ThemeFeatureRow(str(run["data_cutoff_date"]), target_date, int(item["theme_id"]), "", {}, None, actual[int(item["theme_id"])]) for item in method_items]
            rank_scores = [-float(item["predicted_rank"]) for item in method_items]
            predictions = None if any(item["predicted_change_rate"] is None for item in method_items) else [float(item["predicted_change_rate"]) for item in method_items]
            if rows:
                metrics = evaluate_rank_predictions(rows, rank_scores, predictions)
                metrics["evaluable"] = float(len(rows))
                common_actual_order = [theme_id for theme_id in actual_order if theme_id in common_ids]
                metrics["top1_hit"] = _precision([item["theme_id"] for item in sorted(method_items, key=lambda item: item["predicted_rank"])], common_actual_order, 1)
                self._upsert_method_metrics(int(run["id"]), method, str(method_items[0].get("model_version") or ""), metrics, len(method_items), timestamp)
        baseline_items = [item for item in items if item["prediction_method"] == "RULE" and int(item["theme_id"]) in common_ids and item["base_change_rate"] is not None]
        if baseline_items:
            rows = [ThemeFeatureRow(str(run["data_cutoff_date"]), target_date, int(item["theme_id"]), "", {}, None, actual[int(item["theme_id"])]) for item in baseline_items]
            predictions = [float(item["base_change_rate"]) for item in baseline_items]
            metrics = evaluate_rank_predictions(rows, predictions, predictions)
            metrics["evaluable"] = float(len(rows)); metrics["top1_hit"] = None
            self._upsert_method_metrics(int(run["id"]), "BASELINE", "", metrics, len(rows), timestamp)
        self.db.commit()

    def status(self) -> MarketThemeReturnMLStatusResponse:
        model = self._active_model()
        if not model:
            return MarketThemeReturnMLStatusResponse(status="UNAVAILABLE", available=False)
        common = self.db.execute(text("""
            SELECT COUNT(*) common_runs,AVG(r.return_mae) rule_mae,AVG(m.return_mae) ml_mae,
                   AVG(r.precision_at_5) rule_p5,AVG(m.precision_at_5) ml_p5,
                   AVG(r.ndcg_at_5) rule_ndcg,AVG(m.ndcg_at_5) ml_ndcg
              FROM market_theme_return_prediction_method_metrics r
              JOIN market_theme_return_prediction_method_metrics m ON m.run_id=r.run_id AND m.prediction_method='ML'
             WHERE r.prediction_method='RULE'
        """)).mappings().one()
        count = int(common["common_runs"] or 0)
        metrics = {"mae": model["validation_mae"], "rmse": model["validation_rmse"], "mean_signed_gap": model["validation_mean_signed_gap"],
            "direction_accuracy": model["validation_direction_accuracy"], "precision_at_3": model["validation_precision_at_3"],
            "precision_at_5": model["validation_precision_at_5"], "precision_at_10": model["validation_precision_at_10"],
            "spearman": model["validation_spearman"], "ndcg_at_5": model["validation_ndcg_at_5"], "mean_rank_error": model["validation_mean_rank_error"]}
        return MarketThemeReturnMLStatusResponse(status=str(model["status"]), available=True, model_version=str(model["model_version"]),
            model_type=str(model["model_type"]), feature_version=str(model["feature_version"]), trained_at=str(model["trained_at"]),
            train_start_date=str(model["train_start_date"]), train_end_date=str(model["train_end_date"]),
            distinct_train_dates=int(model["distinct_train_dates"]), train_row_count=int(model["train_row_count"]),
            validation_fold_count=int(model["validation_fold_count"]), validation_metrics=metrics,
            rule_metrics={"mae": model["rule_validation_mae"], "precision_at_5": model["rule_validation_precision_at_5"], "ndcg_at_5": model["rule_validation_ndcg_at_5"]},
            baseline_metrics={"mae": model["baseline_validation_mae"], "precision_at_5": model["baseline_validation_precision_at_5"], "ndcg_at_5": model["baseline_validation_ndcg_at_5"]},
            artifact_path=str(model["artifact_path"]), common_evaluated_runs=count,
            cumulative_rule_mae=common["rule_mae"], cumulative_ml_mae=common["ml_mae"],
            cumulative_rule_precision_at_5=common["rule_p5"], cumulative_ml_precision_at_5=common["ml_p5"],
            cumulative_rule_ndcg_at_5=common["rule_ndcg"], cumulative_ml_ndcg_at_5=common["ml_ndcg"],
            promotion_readiness="운영 승격 검토 가능" if count >= 20 else "실전 비교 데이터 부족")
