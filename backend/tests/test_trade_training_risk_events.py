from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.app.repositories.trade_training_repository import TradeTrainingRepository
from backend.app.services.trade_training_service import TradeTrainingService


def build_repository() -> tuple[Session, TradeTrainingRepository]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    db = Session(engine)
    db.execute(text("""
        CREATE TABLE simulation_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL DEFAULT '000000',
            start_date TEXT NOT NULL DEFAULT '2026-01-01',
            end_date TEXT NOT NULL DEFAULT '2026-12-31',
            initial_cash REAL NOT NULL DEFAULT 10000000,
            cash REAL NOT NULL DEFAULT 10000000,
            position_qty INTEGER DEFAULT 0,
            avg_price REAL DEFAULT 0,
            status TEXT DEFAULT '진행중',
            options_json TEXT,
            training_account_id INTEGER,
            updated_at TEXT
        )
    """))
    db.execute(text("""
        CREATE TABLE simulation_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            trade_date TEXT NOT NULL DEFAULT '2026-01-02',
            side TEXT NOT NULL DEFAULT 'BUY',
            price REAL NOT NULL DEFAULT 10000,
            quantity INTEGER NOT NULL DEFAULT 1,
            fee REAL DEFAULT 0,
            amount REAL NOT NULL DEFAULT 10000,
            realized_profit REAL DEFAULT 0,
            reason TEXT,
            method_review_json TEXT,
            created_at TEXT
        )
    """))
    db.commit()
    repo = TradeTrainingRepository(db)
    repo.ensure_training_account_table()
    return db, repo


def risk_event_values() -> dict:
    return {
        "training_account_id": 1,
        "simulation_session_id": 1,
        "risk_scenario_id": 1,
        "risk_scenario_revision_id": 1,
        "risk_plan_step_id": 1,
        "simulation_trade_id": 1,
        "event_key": "simulation_trade:1:risk:PLAN_STEP_EXECUTED",
        "event_type": "PLAN_STEP_EXECUTED",
        "severity": "INFO",
        "planned_value": {"planned_step_price": 10000},
        "actual_value": {"order_price": 10100, "order_quantity": 3},
        "message": "executed",
        "acknowledged": False,
        "acknowledgement_note": None,
        "chart_date": "2026-01-02",
    }


def seed_step_and_trade(db: Session) -> None:
    db.execute(text("""
        INSERT INTO trade_training_risk_plan_steps (
            id, risk_scenario_id, plan_group, plan_type, step_no, status,
            trigger_type, trigger_price, trigger_text, created_at, updated_at
        ) VALUES (1, 1, 'BUY', 'ENTRY', 1, 'PLANNED', 'PRICE_LINE', 10000, '', 'now', 'now')
    """))
    db.execute(text("INSERT INTO simulation_trades (id, session_id) VALUES (1, 1)"))
    db.commit()


def test_risk_step_and_event_rollback_together():
    db, repo = build_repository()
    seed_step_and_trade(db)
    db.info["trade_training_atomic_order"] = True
    repo.execute_risk_plan_step(1, 1, 10100, 3)
    repo.insert_risk_event_no_commit(risk_event_values())
    db.rollback()
    assert db.execute(text("SELECT status FROM trade_training_risk_plan_steps WHERE id = 1")).scalar_one() == "PLANNED"
    assert db.execute(text("SELECT COUNT(*) FROM trade_training_risk_events")).scalar_one() == 0


def test_risk_event_key_is_idempotent_and_step_executes_once():
    db, repo = build_repository()
    seed_step_and_trade(db)
    db.info["trade_training_atomic_order"] = True
    repo.execute_risk_plan_step(1, 1, 10100, 3)
    repo.insert_risk_event_no_commit(risk_event_values())
    repo.insert_risk_event_no_commit(risk_event_values())
    db.commit()
    step = repo.get_risk_plan_step(1)
    assert step is not None
    assert step["status"] == "EXECUTED"
    assert step["actual_price"] == 10100
    assert step["actual_quantity"] == 3
    assert db.execute(text("SELECT COUNT(*) FROM trade_training_risk_events")).scalar_one() == 1

def test_active_plan_update_preserves_executed_step_identity():
    db, repo = build_repository()
    seed_step_and_trade(db)
    db.execute(text("""
        INSERT INTO trade_training_risk_scenarios (
            id, training_account_id, simulation_session_id, cycle_no, status, created_at, updated_at
        ) VALUES (1, 1, 1, 1, 'ACTIVE', 'now', 'now')
    """))
    repo.execute_risk_plan_step(1, 1, 10100, 3)
    db.commit()
    repo.replace_risk_plan_steps(1, [{
        "plan_group": "BUY",
        "plan_type": "ENTRY",
        "step_no": 1,
        "status": "PLANNED",
        "trigger_type": "PRICE_LINE",
        "trigger_price": 9900,
        "trigger_text": "updated",
        "planned_ratio_pct": None,
        "planned_quantity": None,
        "planned_amount": None,
        "memo": None,
        "executed_trade_id": None,
    }])
    db.commit()
    step = repo.get_risk_plan_step(1)
    assert step is not None
    assert step["id"] == 1
    assert step["status"] == "EXECUTED"
    assert step["executed_trade_id"] == 1
    assert step["actual_price"] == 10100
    assert step["actual_quantity"] == 3


def test_active_plan_removal_hides_executed_step_without_losing_execution_history():
    db, repo = build_repository()
    seed_step_and_trade(db)
    db.execute(text("""
        INSERT INTO trade_training_risk_scenarios (
            id, training_account_id, simulation_session_id, cycle_no, status, created_at, updated_at
        ) VALUES (1, 1, 1, 1, 'ACTIVE', 'now', 'now')
    """))
    repo.execute_risk_plan_step(1, 1, 10100, 3)
    db.commit()

    repo.replace_risk_plan_steps(1, [])
    db.commit()

    step = repo.get_risk_plan_step(1)
    assert step is not None
    assert step["status"] == "EXECUTED"
    assert step["is_removed"] == 1
    assert step["executed_trade_id"] == 1
    assert step["actual_price"] == 10100
    assert step["actual_quantity"] == 3

    service = TradeTrainingService(db)
    service.calculate_risk_scenario_preview = lambda *args, **kwargs: {}
    service._holding_risk_summary = lambda *args, **kwargs: None
    detail = service._risk_scenario_detail(repo.get_risk_scenario(1))
    assert detail["buy_steps"] == []

def test_risk_scenario_update_clears_deleted_summary_prices():
    db, repo = build_repository()
    db.execute(text("""
        INSERT INTO trade_training_risk_scenarios (
            id, training_account_id, simulation_session_id, cycle_no, status,
            stop_price, primary_target_price, created_at, updated_at
        ) VALUES (1, 1, 1, 1, 'ACTIVE', 9000, 11000, 'now', 'now')
    """))
    db.commit()

    repo.update_risk_scenario(1, {"stop_price": None, "primary_target_price": None})
    db.commit()

    scenario = repo.get_risk_scenario(1)
    assert scenario is not None
    assert scenario["stop_price"] is None
    assert scenario["primary_target_price"] is None


def test_risk_scenario_detail_excludes_cancelled_steps():
    db, repo = build_repository()
    db.execute(text("""
        INSERT INTO trade_training_risk_scenarios (
            id, training_account_id, simulation_session_id, cycle_no, status, created_at, updated_at
        ) VALUES (1, 1, 1, 1, 'DRAFT', 'now', 'now')
    """))
    db.execute(text("""
        INSERT INTO trade_training_risk_plan_steps (
            id, risk_scenario_id, plan_group, plan_type, step_no, status,
            trigger_type, trigger_price, trigger_text, created_at, updated_at
        ) VALUES
            (1, 1, 'BUY', 'ENTRY', 1, 'PLANNED', 'PRICE_LINE', 10000, '', 'now', 'now'),
            (2, 1, 'SELL', 'STOP_LOSS', 1, 'CANCELLED', 'PRICE_LINE', 9000, '', 'now', 'now')
    """))
    db.commit()
    service = TradeTrainingService(db)
    service.calculate_risk_scenario_preview = lambda *args, **kwargs: {}

    detail = service._risk_scenario_detail(repo.get_risk_scenario(1))

    assert [step["id"] for step in detail["buy_steps"]] == [1]
    assert detail["sell_steps"] == []
