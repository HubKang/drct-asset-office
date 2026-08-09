from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import math
from typing import Any, Callable

import numpy as np
from sklearn.calibration import calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.schemas.market_theme_observation_schema import (
    MarketThemeObservationMLCandidate,
    MarketThemeObservationMLMetrics,
    MarketThemeObservationMLTrainResponse,
)
from backend.app.services.market_theme_observation_feature_service import (
    OBSERVATION_FEATURE_NAMES,
    OBSERVATION_FEATURE_VERSION,
    MarketThemeObservationFeatureService,
)


def _ece(y_true: np.ndarray, probability: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0, 1, bins + 1); total = max(1, len(y_true)); result = 0.0
    for index in range(bins):
        mask = (probability >= edges[index]) & (probability < edges[index + 1] if index < bins - 1 else probability <= edges[index + 1])
        if mask.any():
            result += float(mask.sum()) / total * abs(float(y_true[mask].mean()) - float(probability[mask].mean()))
    return result


def _rank_metrics(rows: list[dict[str, Any]], score_key: str) -> dict[str, float]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["target_date"]].append(row)
    collected: dict[str, list[float]] = defaultdict(list)
    for day_rows in grouped.values():
        ordered = sorted(day_rows, key=lambda row: (-float(row[score_key]), row["theme_id"]))
        actual = sorted(day_rows, key=lambda row: (row["label_rank"], row["theme_id"]))
        actual_rank = {row["theme_id"]: index + 1 for index, row in enumerate(actual)}
        top_actual = {row["theme_id"] for row in day_rows if row["label_top20"] == 1}
        top_count = len(top_actual); top_pred = {row["theme_id"] for row in ordered[:top_count]}
        hits = len(top_pred & top_actual); precision = hits / max(1, len(top_pred)); recall = hits / max(1, len(top_actual))
        collected["precision_top20"].append(precision); collected["recall_top20"].append(recall)
        collected["f1_top20"].append(2 * precision * recall / (precision + recall) if precision + recall else 0)
        collected["precision_at_5"].append(len({row["theme_id"] for row in ordered[:5]} & top_actual) / min(5, len(ordered)))
        dcg = sum((1 if row["theme_id"] in top_actual else 0) / math.log2(index + 2) for index, row in enumerate(ordered[:5]))
        idcg = sum(1 / math.log2(index + 2) for index in range(min(5, len(top_actual))))
        collected["ndcg_at_5"].append(dcg / idcg if idcg else 0)
        predicted_rank = {row["theme_id"]: index + 1 for index, row in enumerate(ordered)}
        n = len(ordered)
        if n > 1:
            collected["spearman"].append(1 - 6 * sum((predicted_rank[row["theme_id"]] - actual_rank[row["theme_id"]]) ** 2 for row in ordered) / (n * (n * n - 1)))
        collected["mean_rank_error"].append(sum(abs(predicted_rank[row["theme_id"]] - actual_rank[row["theme_id"]]) for row in ordered) / n)
    return {key: float(np.mean(values)) for key, values in collected.items() if values}


class MarketThemeObservationMLService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _folds(dates: list[str], count: int = 4) -> list[tuple[list[str], list[str]]]:
        start = max(8, len(dates) // 2); remaining = dates[start:]
        if not remaining:
            return []
        size = max(1, math.ceil(len(remaining) / count)); folds = []
        for index in range(0, len(remaining), size):
            validation = remaining[index:index + size]; train = dates[:start + index]
            if validation and len(train) >= 8:
                folds.append((train, validation))
        return folds

    @staticmethod
    def _model(kind: str) -> Any:
        if kind == "LOGISTIC_TOP20":
            return Pipeline([("imputer", SimpleImputer(strategy="median", add_indicator=True)), ("scale", StandardScaler()),
                             ("model", LogisticRegression(C=.25, max_iter=2000, class_weight="balanced", random_state=42))])
        return Pipeline([("imputer", SimpleImputer(strategy="median", add_indicator=True)),
                         ("model", HistGradientBoostingClassifier(max_iter=120, max_leaf_nodes=12, learning_rate=.04, l2_regularization=1.0, random_state=42))])

    def train(self) -> MarketThemeObservationMLTrainResponse:
        dataset = MarketThemeObservationFeatureService(self.db).build_dataset()
        labeled = [row for row in dataset.rows if row.label_top20 is not None and row.label_rank is not None]
        dates = sorted({row.base_date for row in labeled})
        folds = self._folds(dates)
        if not folds:
            return MarketThemeObservationMLTrainResponse(status="INSUFFICIENT_DATA", message="walk-forward 검증 날짜가 부족합니다.",
                feature_version=OBSERVATION_FEATURE_VERSION, distinct_base_dates=len(dates), train_row_count=len(labeled),
                qualified_date_count=len(dataset.qualified_dates), excluded_universe_dates=dataset.excluded_universe_dates)
        by_date: dict[str, list[Any]] = defaultdict(list)
        for row in labeled: by_date[row.base_date].append(row)
        feature_names = list(OBSERVATION_FEATURE_NAMES)
        all_candidates: list[MarketThemeObservationMLCandidate] = []
        baseline_rows: list[dict[str, Any]] = []
        for _, validation_dates in folds:
            for day in validation_dates:
                for row in by_date[day]:
                    baseline_rows.append({"target_date": row.target_date, "theme_id": row.theme_id, "label_rank": row.label_rank,
                        "label_top20": row.label_top20, "current": row.values.get("base_return_percentile") or 0,
                        "momentum": row.values.get("return_3d_percentile") or 0, "rule": row.observation_rule_score})
        baseline_metrics: dict[str, MarketThemeObservationMLMetrics] = {}
        for name, key in (("CURRENT_RANK", "current"), ("MOMENTUM_3D", "momentum"), ("OBSERVATION_RULE", "rule")):
            baseline_metrics[name] = MarketThemeObservationMLMetrics(**_rank_metrics(baseline_rows, key))
        best_baseline_p = max(float(metric.precision_top20 or 0) for metric in baseline_metrics.values())
        best_baseline_ndcg = max(float(metric.ndcg_at_5 or 0) for metric in baseline_metrics.values())
        for kind in ("LOGISTIC_TOP20", "HGBC_TOP20"):
            predictions: list[dict[str, Any]] = []; fold_improvements = 0
            raw_y: list[int] = []; raw_p: list[float] = []; cal_p: list[float] = []
            for train_dates, validation_dates in folds:
                calibration_size = max(2, math.ceil(len(train_dates) * .20)); model_dates = train_dates[:-calibration_size]; calibration_dates = train_dates[-calibration_size:]
                model_rows = [row for day in model_dates for row in by_date[day]]; calibration_rows = [row for day in calibration_dates for row in by_date[day]]
                validation_rows = [row for day in validation_dates for row in by_date[day]]
                x_model = np.asarray([[row.values.get(name) for name in feature_names] for row in model_rows], dtype=float)
                y_model = np.asarray([row.label_top20 for row in model_rows], dtype=int)
                x_cal = np.asarray([[row.values.get(name) for name in feature_names] for row in calibration_rows], dtype=float)
                y_cal = np.asarray([row.label_top20 for row in calibration_rows], dtype=int)
                x_val = np.asarray([[row.values.get(name) for name in feature_names] for row in validation_rows], dtype=float)
                y_val = np.asarray([row.label_top20 for row in validation_rows], dtype=int)
                if len(np.unique(y_model)) < 2 or len(np.unique(y_cal)) < 2: continue
                model = self._model(kind); model.fit(x_model, y_model)
                cal_raw = np.clip(model.predict_proba(x_cal)[:, 1], 1e-6, 1 - 1e-6)
                calibrator = LogisticRegression(C=1e6, max_iter=1000, random_state=42).fit(np.log(cal_raw / (1 - cal_raw)).reshape(-1, 1), y_cal)
                val_raw = np.clip(model.predict_proba(x_val)[:, 1], 1e-6, 1 - 1e-6)
                val_cal = np.clip(calibrator.predict_proba(np.log(val_raw / (1 - val_raw)).reshape(-1, 1))[:, 1], 1e-6, 1 - 1e-6)
                raw_y.extend(y_val.tolist()); raw_p.extend(val_raw.tolist()); cal_p.extend(val_cal.tolist())
                fold_rows = []
                for row, probability in zip(validation_rows, val_cal):
                    item = {"target_date": row.target_date, "theme_id": row.theme_id, "label_rank": row.label_rank, "label_top20": row.label_top20, "score": float(probability)}
                    predictions.append(item); fold_rows.append(item)
                fold_metric = _rank_metrics(fold_rows, "score")
                rule_fold = _rank_metrics([item for item in baseline_rows if item["target_date"] in {row.target_date for row in validation_rows}], "rule")
                if fold_metric.get("precision_top20", 0) > rule_fold.get("precision_top20", 0): fold_improvements += 1
            if not raw_y: continue
            ranked = _rank_metrics(predictions, "score"); y = np.asarray(raw_y); raw = np.asarray(raw_p); calibrated = np.asarray(cal_p)
            metrics = MarketThemeObservationMLMetrics(**ranked, brier=brier_score_loss(y, calibrated), log_loss=log_loss(y, calibrated),
                calibration_error=_ece(y, calibrated), raw_brier=brier_score_loss(y, raw), raw_log_loss=log_loss(y, raw), raw_calibration_error=_ece(y, raw))
            calibration_pass = float(metrics.calibration_error or 1) <= .15 and float(metrics.brier or 1) <= float(metrics.raw_brier or 0) + .01
            rank_pass = float(metrics.precision_top20 or 0) >= best_baseline_p + .03 and float(metrics.ndcg_at_5 or 0) >= best_baseline_ndcg
            stable = fold_improvements >= math.ceil(len(folds) / 2)
            gate = "PASS" if calibration_pass and rank_pass and stable else "FAIL"
            version = f"OBS-{kind}-V1-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            candidate = MarketThemeObservationMLCandidate(model_type=kind, model_version=version, target_type="TOP20_RELATIVE_STRENGTH",
                selection_gate_status=gate, calibration_status="PASS" if calibration_pass else "FAIL",
                probability_display_mode="PROBABILITY" if calibration_pass else "SCORE", improving_fold_count=fold_improvements,
                validation_fold_count=len(folds), metrics=metrics)
            all_candidates.append(candidate); self._store(candidate, dates, len(labeled))
        self.db.commit()
        return MarketThemeObservationMLTrainResponse(status="COMPLETED", message="Phase4 관찰 모델 후보 학습과 시간순 보정 검증을 완료했습니다.",
            feature_version=OBSERVATION_FEATURE_VERSION, train_start_date=dates[0], train_end_date=dates[-1], distinct_base_dates=len(dates),
            train_row_count=len(labeled), qualified_date_count=len(dataset.qualified_dates), excluded_universe_dates=dataset.excluded_universe_dates,
            validation_fold_count=len(folds), candidates=all_candidates, baseline_metrics=baseline_metrics)

    def _store(self, candidate: MarketThemeObservationMLCandidate, dates: list[str], row_count: int) -> None:
        m = candidate.metrics; now = datetime.now().isoformat(timespec="seconds")
        self.db.execute(text("""
            INSERT INTO market_theme_return_prediction_models
            (model_version,model_type,feature_version,status,trained_at,train_start_date,train_end_date,distinct_train_dates,
             train_row_count,validation_fold_count,artifact_path,created_at,updated_at,target_type,selection_gate_status,
             selection_reason,validation_improving_fold_count,metric_version,validation_precision_at_5,validation_spearman,
             validation_ndcg_at_5,validation_mean_rank_error,validation_precision_top20,validation_recall_top20,validation_f1_top20,
             validation_brier,validation_log_loss,validation_calibration_error,raw_validation_brier,raw_validation_log_loss,
             raw_validation_calibration_error,calibration_status,probability_display_mode)
            VALUES (:version,:kind,:feature,'EXPERIMENTAL',:now,:start,:end,:dates,:rows,:folds,'',:now,:now,
                    'TOP20_RELATIVE_STRENGTH',:gate,:reason,:improving,'THEME_OBSERVATION_METRIC_V1',:p5,:spearman,:ndcg,:rank_error,
                    :p20,:r20,:f1,:brier,:log_loss,:ece,:raw_brier,:raw_log_loss,:raw_ece,:calibration,:display)
        """), {"version": candidate.model_version, "kind": candidate.model_type, "feature": OBSERVATION_FEATURE_VERSION, "now": now,
                "start": dates[0], "end": dates[-1], "dates": len(dates), "rows": row_count, "folds": candidate.validation_fold_count,
                "gate": candidate.selection_gate_status, "reason": "Phase4 Top20·NDCG·fold 안정성·보정 Gate", "improving": candidate.improving_fold_count,
                "p5": m.precision_at_5, "spearman": m.spearman, "ndcg": m.ndcg_at_5, "rank_error": m.mean_rank_error,
                "p20": m.precision_top20, "r20": m.recall_top20, "f1": m.f1_top20, "brier": m.brier, "log_loss": m.log_loss,
                "ece": m.calibration_error, "raw_brier": m.raw_brier, "raw_log_loss": m.raw_log_loss,
                "raw_ece": m.raw_calibration_error, "calibration": candidate.calibration_status, "display": candidate.probability_display_mode})
