from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.services.market_theme_return_prediction_service import MarketThemeReturnPredictionService


@pytest.fixture
def prediction_db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", poolclass=StaticPool)
    with engine.begin() as connection:
        connection.exec_driver_sql("""CREATE TABLE market_themes (
            id INTEGER PRIMARY KEY, theme_name TEXT NOT NULL, parent_theme_id INTEGER, theme_level TEXT NOT NULL DEFAULT 'THEME',
            is_active INTEGER NOT NULL DEFAULT 1, sort_order INTEGER NOT NULL DEFAULT 0)""")
        connection.exec_driver_sql("""CREATE TABLE market_theme_daily_returns (
            id INTEGER PRIMARY KEY AUTOINCREMENT, theme_id INTEGER NOT NULL, return_date TEXT NOT NULL, avg_change_rate REAL,
            stock_count INTEGER NOT NULL, success_stock_count INTEGER NOT NULL, rising_stock_count INTEGER NOT NULL,
            falling_stock_count INTEGER NOT NULL, total_trading_value_100m REAL, last_refreshed_at TEXT,
            UNIQUE(theme_id, return_date))""")
        connection.exec_driver_sql("CREATE TABLE market_theme_stocks (id INTEGER PRIMARY KEY, theme_id INTEGER, stock_id INTEGER, is_active INTEGER)")
        connection.exec_driver_sql("""CREATE TABLE stock_investor_flows (
            id INTEGER PRIMARY KEY, stock_id INTEGER, flow_date TEXT, foreign_net_amount INTEGER,
            institution_net_amount INTEGER, program_net_amount INTEGER)""")
        connection.exec_driver_sql("""CREATE TABLE market_theme_stock_daily_returns (
            id INTEGER PRIMARY KEY, theme_id INTEGER, stock_id INTEGER, return_date TEXT, trading_value INTEGER)""")
        connection.exec_driver_sql("""CREATE TABLE market_theme_return_prediction_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,target_date TEXT NOT NULL,data_cutoff_date TEXT NOT NULL,data_cutoff_at TEXT,
            prediction_stage TEXT NOT NULL,prediction_horizon TEXT NOT NULL,official_method TEXT NOT NULL,status TEXT NOT NULL,
            revision_count INTEGER NOT NULL,rule_version TEXT NOT NULL,model_version TEXT,first_predicted_at TEXT NOT NULL,
            last_predicted_at TEXT NOT NULL,evaluated_at TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
            UNIQUE(target_date,prediction_stage,prediction_horizon))""")
        connection.exec_driver_sql("""CREATE TABLE market_theme_return_prediction_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,run_id INTEGER NOT NULL,theme_id INTEGER NOT NULL,prediction_method TEXT NOT NULL,
            is_official INTEGER NOT NULL,model_version TEXT,base_change_rate REAL,predicted_change_rate REAL,prediction_score REAL,predicted_rank INTEGER,
            price_score REAL,flow_score REAL,breadth_score REAL,alignment_score REAL,liquidity_score REAL,market_environment_score REAL,
            penalty_score REAL,data_coverage_rate REAL,actual_change_rate REAL,actual_rank INTEGER,signed_gap REAL,absolute_gap REAL,
            rank_gap INTEGER,direction_hit INTEGER,baseline_absolute_error REAL,prediction_effect REAL,evaluation_status TEXT,
            evaluated_at TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,UNIQUE(run_id,theme_id,prediction_method))""")
        connection.exec_driver_sql("""CREATE TABLE market_theme_return_prediction_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,run_id INTEGER NOT NULL UNIQUE,theme_count INTEGER,evaluable_theme_count INTEGER,
            return_mae REAL,return_rmse REAL,mean_signed_gap REAL,mean_rank_error REAL,top1_hit REAL,precision_at_3 REAL,
            precision_at_5 REAL,precision_at_10 REAL,direction_accuracy REAL,spearman_rank_correlation REAL,ndcg_at_5 REAL,
            baseline_mae REAL,mae_improvement REAL,baseline_precision_at_5 REAL,improved_theme_count INTEGER,evaluation_status TEXT,
            evaluated_at TEXT,created_at TEXT,updated_at TEXT)""")
        connection.exec_driver_sql("""CREATE TABLE market_theme_return_prediction_models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,model_version TEXT UNIQUE,model_type TEXT,feature_version TEXT,status TEXT,
            trained_at TEXT,train_start_date TEXT,train_end_date TEXT,distinct_train_dates INTEGER,train_row_count INTEGER,
            validation_fold_count INTEGER,validation_mae REAL,validation_rmse REAL,validation_mean_signed_gap REAL,
            validation_direction_accuracy REAL,validation_precision_at_3 REAL,validation_precision_at_5 REAL,
            validation_precision_at_10 REAL,validation_spearman REAL,validation_ndcg_at_5 REAL,validation_mean_rank_error REAL,
            rule_validation_mae REAL,rule_validation_precision_at_5 REAL,rule_validation_ndcg_at_5 REAL,
            baseline_validation_mae REAL,baseline_validation_precision_at_5 REAL,baseline_validation_ndcg_at_5 REAL,
            artifact_path TEXT,sklearn_version TEXT,created_at TEXT,updated_at TEXT)""")
        connection.exec_driver_sql("""CREATE TABLE market_theme_return_prediction_method_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,run_id INTEGER,prediction_method TEXT,model_version TEXT DEFAULT '',
            theme_count INTEGER,evaluable_theme_count INTEGER,return_mae REAL,return_rmse REAL,mean_signed_gap REAL,
            mean_rank_error REAL,top1_hit REAL,precision_at_3 REAL,precision_at_5 REAL,precision_at_10 REAL,
            direction_accuracy REAL,spearman_rank_correlation REAL,ndcg_at_5 REAL,evaluated_at TEXT,created_at TEXT,updated_at TEXT,
            UNIQUE(run_id,prediction_method,model_version))""")
        connection.exec_driver_sql("""CREATE TABLE market_theme_return_prediction_rule_sets (
            id INTEGER PRIMARY KEY,rule_version TEXT,name TEXT,status TEXT,is_active INTEGER,created_at TEXT,updated_at TEXT)""")
        connection.exec_driver_sql("""CREATE TABLE market_theme_return_prediction_rule_parameters (
            id INTEGER PRIMARY KEY,rule_set_id INTEGER,parameter_code TEXT,parameter_value REAL,description TEXT,created_at TEXT,updated_at TEXT)""")
        connection.exec_driver_sql("INSERT INTO market_theme_return_prediction_rule_sets VALUES (1,'RULE_V1','V1','ACTIVE',1,'2026-01-01','2026-01-01')")
        parameters = {"PRICE_WEIGHT": .25, "FLOW_WEIGHT": .25, "BREADTH_WEIGHT": .15, "ALIGNMENT_WEIGHT": .15,
                      "LIQUIDITY_WEIGHT": .1, "MARKET_ENVIRONMENT_WEIGHT": .1, "OVERHEAT_PENALTY_MAX": 15,
                      "CONCENTRATION_PENALTY_MAX": 10, "LOW_COVERAGE_PENALTY_MAX": 20,
                      "FLOW_DIVERGENCE_PENALTY_MAX": 10, "MIN_DATA_COVERAGE": .7, "PREDICTION_SCALE": 1,
                      "PREDICTION_BIAS": 0, "PREDICTION_MIN": -20, "PREDICTION_MAX": 20, "DIRECTION_NEUTRAL_BAND": .5}
        connection.exec_driver_sql("INSERT INTO market_theme_return_prediction_rule_parameters VALUES (?,?,?,?,?,?,?)",
            [(index, 1, code, value, code, "2026-01-01", "2026-01-01") for index, (code, value) in enumerate(parameters.items(), 1)])
        connection.exec_driver_sql("INSERT INTO market_themes VALUES (10,'그룹',NULL,'THEME_GROUP',1,0)")
        connection.exec_driver_sql("INSERT INTO market_themes VALUES (1,'반도체',10,'THEME',1,1),(2,'로봇',10,'THEME',1,2),(3,'바이오',10,'THEME',1,3)")
        for theme_id in (1, 2, 3):
            connection.exec_driver_sql("INSERT INTO market_theme_stocks VALUES (?,?,?,1)", (theme_id, theme_id, theme_id))
        start = date(2026, 7, 20)
        row_id = 1
        for offset in range(10):
            day = (start + timedelta(days=offset)).isoformat()
            for theme_id, rate in ((1, .4 + offset * .12), (2, .2 + offset * .05), (3, -.2 + offset * .02)):
                connection.exec_driver_sql("INSERT INTO market_theme_daily_returns VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (row_id, theme_id, day, rate, 4, 4, 3 if rate > 0 else 1, 1 if rate > 0 else 3, 100 + theme_id * 20, f"{day} 18:00:00"))
                row_id += 1
            connection.exec_driver_sql("INSERT INTO stock_investor_flows VALUES (?,?,?,?,?,?)",
                (offset * 3 + 1, 1, day, 1_000_000 + offset * 10_000, 500_000, 100_000))
            connection.exec_driver_sql("INSERT INTO stock_investor_flows VALUES (?,?,?,?,?,?)",
                (offset * 3 + 2, 2, day, 200_000, 100_000, 0))
            connection.exec_driver_sql("INSERT INTO stock_investor_flows VALUES (?,?,?,?,?,?)",
                (offset * 3 + 3, 3, day, -300_000, -100_000, -50_000))
        cutoff = (start + timedelta(days=9)).isoformat()
        connection.exec_driver_sql("INSERT INTO market_theme_stock_daily_returns VALUES (1,1,1,?,100000000),(2,2,2,?,100000000),(3,3,3,?,100000000)", (cutoff, cutoff, cutoff))
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_prediction_upsert_ranking_and_query_bound(prediction_db: Session) -> None:
    statements: list[str] = []
    event.listen(prediction_db.bind, "before_cursor_execute", lambda *_args: statements.append(str(_args[2])))
    service = MarketThemeReturnPredictionService(prediction_db)
    first = service.predict("2026-07-30")
    assert first.run and first.run.revision_count == 1
    assert [item.theme_name for item in first.items] == ["반도체", "로봇", "바이오"]
    assert [item.predicted_rank for item in first.items] == [1, 2, 3]
    first_predicted_at = first.run.first_predicted_at
    before_second = len(statements)
    second = service.predict("2026-07-30")
    assert second.run and second.run.revision_count == 2
    assert second.run.first_predicted_at == first_predicted_at
    # Reads and writes are batch-oriented; query count does not grow per theme.
    assert len(statements) - before_second < 25


def test_waiting_actual_then_validation_metrics(prediction_db: Session) -> None:
    service = MarketThemeReturnPredictionService(prediction_db)
    service.predict("2026-07-30")
    waiting = service.validate("2026-07-30")
    assert waiting.status == "WAITING_ACTUAL"
    prediction_db.execute(__import__("sqlalchemy").text("""INSERT INTO market_theme_daily_returns
        (theme_id,return_date,avg_change_rate,stock_count,success_stock_count,rising_stock_count,falling_stock_count,total_trading_value_100m,last_refreshed_at)
        VALUES (1,'2026-07-30',2.1,4,4,3,1,150,'2026-07-30 18:00:00'),
               (2,'2026-07-30',0.7,4,4,3,1,120,'2026-07-30 18:00:00'),
               (3,'2026-07-30',-0.5,4,4,1,3,90,'2026-07-30 18:00:00')"""))
    prediction_db.commit()
    evaluated = service.validate("2026-07-30")
    assert evaluated.status == "EVALUATED"
    assert evaluated.metrics and evaluated.metrics.evaluable_theme_count == 3
    assert evaluated.metrics.return_mae is not None
    assert all(item.absolute_gap == pytest.approx(abs(item.actual_change_rate - item.predicted_change_rate)) for item in evaluated.items)
    assert all(item.prediction_effect == pytest.approx(item.baseline_absolute_error - item.absolute_gap) for item in evaluated.items)
    with pytest.raises(HTTPException) as blocked:
        service.predict("2026-07-30")
    assert blocked.value.status_code == 409


@pytest.mark.parametrize("target", ["2026-08-01", "2026-08-02", "2026-07-29"])
def test_invalid_target_dates_are_rejected(prediction_db: Session, target: str) -> None:
    with pytest.raises(HTTPException) as raised:
        MarketThemeReturnPredictionService(prediction_db).predict(target)
    assert raised.value.status_code == 400
