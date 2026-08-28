from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.app.repositories.trade_training_repository import TradeTrainingRepository
from backend.app.schemas.trade_training_schema import TrainingOrderRequest
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
        "event_key": "simulation_trade:1:risk:UNPLANNED_BUY",
        "event_type": "UNPLANNED_BUY",
        "severity": "CAUTION",
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


def test_technical_risk_event_is_not_persisted_and_payload_is_allowlisted():
    db, repo = build_repository()
    values = risk_event_values()
    technical = {**values, "event_key": "technical:1", "event_type": "PLAN_STEP_EXECUTED"}

    assert repo.insert_risk_event_no_commit(technical) == {}
    assert db.execute(text("SELECT COUNT(*) FROM trade_training_risk_events")).scalar_one() == 0

    values["actual_value"] = {
        "order_price": 10100,
        "order_quantity": 3,
        "unplanned_reason": "계획 변경",
        "post_position_quantity": 99,
        "raw_response": {"large": "payload"},
    }
    stored = repo.insert_risk_event_no_commit(values)
    db.commit()

    assert stored["id"]
    decoded = repo.get_risk_event(int(stored["id"]))
    assert decoded is not None
    assert decoded["actual_value"] == {
        "order_price": 10100,
        "order_quantity": 3,
        "unplanned_reason": "계획 변경",
    }


def test_planned_order_updates_step_without_persisting_technical_events():
    db, repo = build_repository()
    seed_step_and_trade(db)
    service = TradeTrainingService(db)
    service._record_order_risk_events(
        {"id": 1, "training_account_id": 1},
        TrainingOrderRequest(price=10100, quantity=3, risk_plan_step_id=1),
        {"id": 1, "side": "BUY", "trade_date": "2026-01-02"},
        {
            "selected_step": {"id": 1, "trigger_price": 10000},
            "warnings": [],
            "risk_budget_amount": 100000,
            "stop_price": 9000,
            "projected_estimated_risk": 90000,
            "risk_usage_pct": 90,
        },
        1,
        1,
    )
    db.commit()

    assert repo.get_risk_plan_step(1)["status"] == "EXECUTED"
    assert db.execute(text("SELECT COUNT(*) FROM trade_training_risk_events")).scalar_one() == 0

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


def seed_active_reach_scenario(db: Session) -> None:
    db.execute(text("""
        INSERT INTO simulation_sessions (
            id, stock_code, start_date, end_date, initial_cash, cash, position_qty,
            avg_price, status, options_json, training_account_id
        ) VALUES (1, '000001', '2026-01-01', '2026-01-31', 10000000, 9000000, 10, 10000, '진행중', '{}', 1)
    """))
    db.execute(text("""
        INSERT INTO trade_training_risk_scenarios (
            id, training_account_id, simulation_session_id, cycle_no, status,
            created_at, updated_at
        ) VALUES (1, 1, 1, 1, 'ACTIVE', 'now', 'now')
    """))
    db.execute(text("""
        INSERT INTO trade_training_risk_plan_steps (
            id, risk_scenario_id, plan_group, plan_type, step_no, status,
            trigger_type, trigger_price, trigger_text, created_at, updated_at
        ) VALUES
            (1, 1, 'BUY', 'ENTRY', 1, 'EXECUTED', 'PRICE_LINE', 10000, '', 'now', 'now'),
            (2, 1, 'SELL', 'TAKE_PROFIT', 1, 'PLANNED', 'PRICE_LINE', 11000, '', 'now', 'now'),
            (3, 1, 'SELL', 'PARTIAL_STOP', 2, 'PLANNED', 'PRICE_LINE', 9500, '', 'now', 'now'),
            (4, 1, 'SELL', 'FULL_STOP', 3, 'PLANNED', 'PRICE_LINE', 9000, '', 'now', 'now')
    """))
    db.commit()


def test_execution_review_excludes_non_applicable_split_entry():
    db, repo = build_repository()
    seed_active_reach_scenario(db)
    service = TradeTrainingService(db)
    service._session_prices = lambda session: []

    review = service.get_risk_scenario_execution_review(1)

    split_entry = next(row for row in review["category_scores"] if row["key"] == "split_entry")
    assert split_entry["applicable"] is False
    assert split_entry["score"] is None
    assert review["overall_execution_rate"] is not None

def test_delete_training_account_removes_scenario_habit_data():
    db, repo = build_repository()
    db.execute(text("CREATE TABLE IF NOT EXISTS simulation_snapshots (id INTEGER PRIMARY KEY, session_id INTEGER NOT NULL)"))
    db.execute(text("CREATE TABLE IF NOT EXISTS simulation_reviews (id INTEGER PRIMARY KEY, session_id INTEGER NOT NULL)"))
    db.execute(text("""
        INSERT INTO trade_training_accounts (
            id, name, status, initial_capital, cash_balance, realized_equity,
            commission_rate, risk_per_trade_pct, max_open_risk_pct, max_position_count,
            display_days_default, moving_average_periods_default, created_at, updated_at
        ) VALUES (1, 'delete target', 'ACTIVE', 10000000, 9000000, 10000000,
                  0.001, 1, 3, 5, 80, '[5,10,20,60,120]', 'now', 'now')
    """))
    db.execute(text("INSERT INTO simulation_sessions (id, training_account_id) VALUES (1, 1)"))
    db.execute(text("INSERT INTO simulation_trades (id, session_id) VALUES (1, 1)"))
    db.execute(text("INSERT INTO simulation_snapshots (id, session_id) VALUES (1, 1)"))
    db.execute(text("INSERT INTO simulation_reviews (id, session_id) VALUES (1, 1)"))
    db.execute(text("""
        INSERT INTO trade_training_account_ledger (
            id, training_account_id, simulation_session_id, simulation_trade_id,
            event_type, event_key, cash_before, cash_after, created_at
        ) VALUES (1, 1, 1, 1, 'BUY', 'delete:1', 10000000, 9000000, 'now')
    """))
    db.execute(text("""
        INSERT INTO trade_training_risk_scenarios (
            id, training_account_id, simulation_session_id, cycle_no, status,
            buy_plan_mode, sell_plan_mode, created_at, updated_at
        ) VALUES (1, 1, 1, 1, 'CLOSED', 'SINGLE', 'SPLIT', 'now', 'now')
    """))
    db.execute(text("""
        INSERT INTO trade_training_risk_plan_steps (
            id, risk_scenario_id, plan_group, plan_type, step_no, status,
            trigger_type, trigger_text, created_at, updated_at
        ) VALUES (1, 1, 'SELL', 'TAKE_PROFIT', 1, 'EXECUTED', 'PRICE_LINE', '', 'now', 'now')
    """))
    db.execute(text("""
        INSERT INTO trade_training_risk_scenario_revisions (
            id, risk_scenario_id, revision_no, revision_type,
            snapshot_json, effective_from, created_at
        ) VALUES (1, 1, 1, 'CREATED', '{}', '2026-01-01', 'now')
    """))
    db.execute(text("""
        INSERT INTO trade_training_risk_events (
            id, training_account_id, simulation_session_id, risk_scenario_id,
            event_key, event_type, severity, message, created_at
        ) VALUES (1, 1, 1, 1, 'delete:event:1', 'TAKE_PROFIT_REACHED', 'INFO', '', 'now')
    """))
    db.commit()

    counts = repo.delete_training_account(1)

    assert counts == {
        "session_count": 1,
        "trade_count": 1,
        "snapshot_count": 1,
        "review_count": 1,
        "risk_scenario_count": 1,
        "risk_plan_step_count": 1,
        "risk_revision_count": 1,
        "risk_event_count": 1,
    }
    for table in (
        "trade_training_risk_events",
        "trade_training_risk_scenario_revisions",
        "trade_training_risk_plan_steps",
        "trade_training_risk_scenarios",
        "simulation_reviews",
        "simulation_snapshots",
        "simulation_trades",
        "simulation_sessions",
        "trade_training_account_ledger",
        "trade_training_accounts",
    ):
        assert db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one() == 0
