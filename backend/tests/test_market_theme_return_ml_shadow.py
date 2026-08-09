from __future__ import annotations

from datetime import date, timedelta
import math

import numpy as np
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.app.services.market_theme_return_feature_service import (
    FEATURE_NAMES,
    FEATURE_VERSION,
    MarketThemeReturnFeatureService,
    ThemeFeatureDataset,
    ThemeFeatureRow,
)
from backend.app.services.market_theme_return_ml_service import (
    MarketThemeReturnMLService,
    _MODEL_CACHE,
    evaluate_predictions,
)
from backend.app.services.market_theme_return_prediction_service import MarketThemeReturnPredictionService
from backend.tests.test_market_theme_return_prediction_phase1 import prediction_db


def _feature_values(seed: float, gap: float = 1.0) -> dict[str, float | None]:
    values = {name: seed + index * .01 for index, name in enumerate(FEATURE_NAMES)}
    values["data_coverage_rate"] = .95
    values["base_change_rate"] = seed
    values["calendar_gap_days"] = gap
    values["program_flow_strength"] = None if int(seed * 10) % 3 == 0 else seed * .01
    return values


def _synthetic_dataset(days: int = 80, themes: int = 10) -> ThemeFeatureDataset:
    rows: list[ThemeFeatureRow] = []
    start = date(2025, 1, 1)
    actual_dates = [(start + timedelta(days=index)).isoformat() for index in range(days + 1)]
    for day_index in range(days):
        for theme_id in range(1, themes + 1):
            signal = math.sin(day_index / 5) + theme_id * .08
            label = signal * 1.3 + math.cos(theme_id)
            rows.append(ThemeFeatureRow(actual_dates[day_index], actual_dates[day_index + 1], theme_id,
                f"theme-{theme_id}", _feature_values(signal), signal, label))
    return ThemeFeatureDataset(rows, actual_dates, 3, 7)


def test_dataset_uses_next_observed_date_and_dated_snapshots_only() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE market_themes(id INTEGER PRIMARY KEY,theme_name TEXT)")
        connection.exec_driver_sql("""CREATE TABLE market_theme_daily_returns(
            theme_id INTEGER,return_date TEXT,avg_change_rate REAL,stock_count INTEGER,success_stock_count INTEGER,
            rising_stock_count INTEGER,falling_stock_count INTEGER,flat_stock_count INTEGER,total_trading_value_100m REAL)""")
        connection.exec_driver_sql("""CREATE TABLE market_theme_stock_daily_returns(
            theme_id INTEGER,stock_id INTEGER,return_date TEXT,trading_value INTEGER)""")
        connection.exec_driver_sql("""CREATE TABLE stock_investor_flows(
            stock_id INTEGER,flow_date TEXT,foreign_net_amount INTEGER,institution_net_amount INTEGER,program_net_amount INTEGER)""")
        connection.exec_driver_sql("CREATE TABLE market_theme_stocks(theme_id INTEGER,stock_id INTEGER,is_active INTEGER)")
        connection.exec_driver_sql("INSERT INTO market_themes VALUES (1,'A'),(2,'B')")
        connection.exec_driver_sql("INSERT INTO market_theme_stocks VALUES (1,999,1),(2,998,1)")
        dates = ["2026-01-02", "2026-01-05", "2026-01-07"]
        for day_index, day in enumerate(dates):
            for theme_id in (1, 2):
                connection.exec_driver_sql("INSERT INTO market_theme_daily_returns VALUES (?,?,?,?,?,?,?,?,?)",
                    (theme_id, day, day_index + theme_id / 10, 1, 1, 1, 0, 0, 10))
                stock_id = theme_id * 10
                connection.exec_driver_sql("INSERT INTO market_theme_stock_daily_returns VALUES (?,?,?,?)", (theme_id, stock_id, day, 1_000_000))
                connection.exec_driver_sql("INSERT INTO stock_investor_flows VALUES (?,?,?,?,?)", (stock_id, day, 100, 50, 10))
    with Session(engine) as session:
        dataset = MarketThemeReturnFeatureService(session).build_dataset(min_coverage=.7)
    friday = next(row for row in dataset.rows if row.base_date == "2026-01-02" and row.theme_id == 1)
    monday = next(row for row in dataset.rows if row.base_date == "2026-01-05" and row.theme_id == 1)
    assert friday.target_date == "2026-01-05" and friday.values["calendar_gap_days"] == 3
    assert monday.target_date == "2026-01-07" and monday.values["calendar_gap_days"] == 2
    assert friday.label == pytest.approx(1.1)
    assert friday.values["joint_flow_strength"] is not None
    # The deliberately wrong current links (998/999) are never used for historical features.
    assert len(dataset.rows) == 4
    engine.dispose()


def test_models_fit_with_fold_local_preprocessing_and_rank_selection() -> None:
    dataset = _synthetic_dataset(50, 10)
    train_rows = [row for row in dataset.rows if row.base_date < dataset.actual_dates[40]]
    validation_rows = [row for row in dataset.rows if row.base_date >= dataset.actual_dates[40]]
    x_train = MarketThemeReturnMLService._matrix(train_rows)
    x_validation = MarketThemeReturnMLService._matrix(validation_rows)
    y_train = np.asarray([row.label for row in train_rows], dtype=float)
    ridge = MarketThemeReturnMLService._ridge().fit(x_train, y_train)
    boosting = MarketThemeReturnMLService._boosting().fit(x_train, y_train)
    assert ridge.named_steps["imputer"].statistics_.shape[0] == len(FEATURE_NAMES)
    ridge_metrics = evaluate_predictions(validation_rows, ridge.predict(x_validation).tolist())
    boosting_metrics = evaluate_predictions(validation_rows, boosting.predict(x_validation).tolist())
    assert ridge_metrics["mae"] is not None and boosting_metrics["ndcg_at_5"] is not None
    chosen = min((("RIDGE", ridge_metrics), ("HGBR", boosting_metrics)), key=MarketThemeReturnMLService._selection_key)
    assert chosen[0] in {"RIDGE", "HGBR"}


def test_training_versions_and_shadow_do_not_modify_rule(prediction_db: Session, tmp_path, monkeypatch) -> None:
    dataset = _synthetic_dataset()
    monkeypatch.setattr(MarketThemeReturnFeatureService, "build_dataset", lambda self, **_kwargs: dataset)
    monkeypatch.setattr("backend.app.services.market_theme_return_ml_service.MODEL_ARTIFACT_DIR", tmp_path)
    rule_service = MarketThemeReturnPredictionService(prediction_db)
    before = rule_service.predict("2026-07-30")
    assert before.run
    rule_snapshot = [(item.theme_id, item.predicted_rank, item.predicted_change_rate) for item in before.items]
    revision = before.run.revision_count
    ml_service = MarketThemeReturnMLService(prediction_db)
    first = ml_service.train_shadow()
    second = ml_service.train_shadow()
    assert first.model_version != second.model_version
    assert first.artifact_path and second.artifact_path
    assert first.status == second.status == "SHADOW"
    statuses = prediction_db.execute(text("SELECT status FROM market_theme_return_prediction_models ORDER BY id")).scalars().all()
    assert statuses == ["RETIRED", "SHADOW"]
    inference_rows = [ThemeFeatureRow("2026-07-29", "2026-07-30", theme_id, f"theme-{theme_id}", _feature_values(theme_id / 10), None)
                      for theme_id in (1, 2, 3)]
    monkeypatch.setattr(MarketThemeReturnFeatureService, "build_for_date", lambda self, *_args, **_kwargs: inference_rows)
    after = ml_service.predict_shadow("2026-07-30")
    assert after.run and after.run.revision_count == revision
    assert [(item.theme_id, item.predicted_rank, item.predicted_change_rate) for item in after.items] == rule_snapshot
    assert len(after.shadow_items) == 3
    assert all(item.prediction_method == "ML" and item.is_official is False and item.model_version == second.model_version for item in after.shadow_items)
    prediction_db.execute(text("""INSERT INTO market_theme_daily_returns
        (theme_id,return_date,avg_change_rate,stock_count,success_stock_count,rising_stock_count,falling_stock_count,total_trading_value_100m,last_refreshed_at)
        VALUES (1,'2026-07-30',1.2,4,4,3,1,100,'2026-07-30 18:00:00'),
               (2,'2026-07-30',0.4,4,4,2,2,100,'2026-07-30 18:00:00'),
               (3,'2026-07-30',-0.8,4,4,1,3,100,'2026-07-30 18:00:00')"""))
    prediction_db.commit()
    evaluated = rule_service.validate("2026-07-30")
    assert {metric.prediction_method for metric in evaluated.method_metrics} == {"BASELINE", "RULE", "ML"}
    assert all(item.actual_change_rate is not None for item in evaluated.shadow_items)
    prediction_db.execute(text("UPDATE market_theme_return_prediction_models SET artifact_path='missing.joblib' WHERE status='SHADOW'"))
    prediction_db.commit(); _MODEL_CACHE.clear()
    assert ml_service.predict_shadow("2026-07-30", require_model=False) is None
    protected = rule_service.get("2026-07-30")
    assert [(item.theme_id, item.predicted_rank, item.predicted_change_rate) for item in protected.items] == rule_snapshot
