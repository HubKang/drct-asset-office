from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.app.repositories.trade_training_repository import TradeTrainingRepository
from backend.app.services.trade_training_service import TradeTrainingService


def build_repository() -> tuple[Session, TradeTrainingRepository]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    db = Session(engine)
    db.execute(text("""
        CREATE TABLE simulation_sessions (
            id INTEGER PRIMARY KEY,
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
            id INTEGER PRIMARY KEY,
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
            client_order_id TEXT,
            created_at TEXT
        )
    """))
    db.commit()
    repo = TradeTrainingRepository(db)
    repo.ensure_training_account_table()
    return db, repo


def scenario_values(session_id: int, cycle_no: int) -> dict:
    return {
        "training_account_id": 1,
        "simulation_session_id": session_id,
        "cycle_no": cycle_no,
        "status": "DRAFT",
        "buy_plan_mode": "SINGLE",
        "sell_plan_mode": "SPLIT",
        "risk_basis_equity": 10_000_000,
        "account_risk_pct": 1,
        "risk_budget_amount": 100_000,
        "profit_scenario_text": "목표가에서 분할매도",
        "stop_scenario_text": "전량 손절가 이탈 시 청산",
        "stop_price": 9_000,
        "primary_target_price": 11_000,
        "estimated_planned_loss": 100_000,
        "estimated_risk_usage_pct": 100,
        "memo": None,
    }


def activation_values() -> dict:
    return {
        "risk_basis_equity": 10_000_000,
        "account_risk_pct": 1,
        "risk_budget_amount": 100_000,
        "estimated_planned_loss": 100_000,
        "estimated_risk_usage_pct": 100,
    }


def test_closed_scenario_is_never_reactivated_and_reentry_uses_new_cycle() -> None:
    db, repo = build_repository()
    first = repo.create_risk_scenario(scenario_values(session_id=1, cycle_no=1))
    active = repo.activate_risk_scenario(first["id"], activation_values())
    assert active["status"] == "ACTIVE"

    closed = repo.close_risk_scenario(
        first["id"],
        {"closed_trade_id": "1-10", "final_trade_id": 10, "final_net_pnl": 50_000, "final_return_pct": 0.5},
    )
    db.commit()
    assert closed["status"] == "CLOSED"
    assert closed["closed_at"] is not None
    assert repo.get_current_risk_scenario(1) is None

    unchanged = repo.activate_risk_scenario(first["id"], activation_values())
    assert unchanged["status"] == "CLOSED"

    second = repo.create_risk_scenario(scenario_values(session_id=1, cycle_no=repo.get_next_risk_scenario_cycle_no(1)))
    db.commit()
    assert second["id"] != first["id"]
    assert second["cycle_no"] == 2
    assert second["status"] == "DRAFT"
    assert repo.get_current_risk_scenario(1)["id"] == second["id"]


def test_active_scenario_remains_active_until_explicit_close() -> None:
    db, repo = build_repository()
    scenario = repo.create_risk_scenario(scenario_values(session_id=2, cycle_no=1))
    repo.activate_risk_scenario(scenario["id"], activation_values())
    db.commit()

    current = repo.get_active_risk_scenario(2)
    assert current is not None
    assert current["id"] == scenario["id"]
    assert current["status"] == "ACTIVE"


def test_position_with_missing_active_scenario_recovers_from_draft() -> None:
    class RecoveryRepository:
        def __init__(self) -> None:
            self.activated_id: int | None = None

        def get_active_risk_scenario(self, _session_id: int):
            return None

        def get_draft_risk_scenario(self, _session_id: int):
            return {"id": 22, "status": "DRAFT", "stop_price": 9_000}

        def list_risk_plan_steps(self, _scenario_id: int):
            return [
                {"id": 31, "plan_group": "BUY", "plan_type": "ENTRY", "step_no": 1, "trigger_price": 10_000},
                {"id": 32, "plan_group": "SELL", "plan_type": "FULL_STOP", "step_no": 2, "trigger_price": 9_000},
            ]

        def activate_risk_scenario(self, scenario_id: int, _preview: dict):
            self.activated_id = scenario_id
            return {"id": scenario_id, "status": "ACTIVE"}

        def create_risk_scenario_revision(self, scenario_id: int, revision_type: str, _snapshot: dict, _reason: str):
            assert scenario_id == 22
            assert revision_type == "RECOVERY_ACTIVATE"
            return {"id": 44}

    service = TradeTrainingService.__new__(TradeTrainingService)
    service.repo = RecoveryRepository()  # type: ignore[assignment]
    service.calculate_risk_scenario_preview = lambda *args, **kwargs: {  # type: ignore[method-assign]
        "risk_basis_equity": 10_000_000,
        "account_risk_pct": 1,
        "risk_budget_amount": 100_000,
        "estimated_planned_loss": 100_000,
        "estimated_risk_usage_pct": 100,
        "warnings": [],
    }
    service._risk_snapshot = lambda *args, **kwargs: {}  # type: ignore[method-assign]

    active, revision_id, step_id = service.activate_risk_scenario_for_first_buy(
        {"id": 7, "training_account_id": 1, "position_qty": 10},
        {"risk_plan_step_id": None},
    )

    assert active == {"id": 22, "status": "ACTIVE"}
    assert revision_id == 44
    assert step_id == 31
    assert service.repo.activated_id == 22  # type: ignore[attr-defined]
