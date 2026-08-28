from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.app.repositories.trade_training_repository import TradeTrainingRepository
from backend.app.schemas.trade_training_schema import TradeTrainingRiskScenarioDraftRequest
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
            created_at TEXT,
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


def test_next_day_does_not_check_or_create_plan_price_reach_alerts() -> None:
    class NextDayRepository:
        def get_session(self, _session_id: int):
            return {"id": 7, "status": "진행중", "current_index": 0}

        def update_session(self, _session_id: int, values: dict):
            return {"id": 7, "status": values.get("status", "진행중"), **values}

    service = TradeTrainingService.__new__(TradeTrainingService)
    service.repo = NextDayRepository()  # type: ignore[assignment]
    service._session_prices = lambda _session: [  # type: ignore[method-assign]
        {"trade_date": "2026-01-02"},
        {"trade_date": "2026-01-05"},
        {"trade_date": "2026-01-06"},
    ]
    service._save_snapshot = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
    service.get_session_detail = lambda _session_id: {  # type: ignore[method-assign]
        "session": {"id": 7, "current_date": "2026-01-05", "status": "진행중"}
    }
    service.check_risk_level_reaches = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("removed reach feature was called"))  # type: ignore[attr-defined]

    detail = service.next_day(7)

    assert detail["session"]["current_date"] == "2026-01-05"


def test_active_scenario_price_reset_soft_removes_every_saved_line() -> None:
    db, repo = build_repository()
    account = repo.create_training_account({
        "name": "가격 초기화 테스트",
        "description": "",
        "initial_capital": 10_000_000,
        "commission_rate": 0,
        "risk_per_trade_pct": 1,
        "max_open_risk_pct": 5,
        "max_position_count": 5,
        "display_days_default": 80,
        "moving_average_periods_default": [5, 10, 20, 60, 120],
    })
    db.execute(text("""
        INSERT INTO simulation_sessions (
            id, stock_code, start_date, end_date, initial_cash, cash,
            position_qty, avg_price, status, training_account_id
        ) VALUES (3, '211270', '2026-01-01', '2026-12-31', 10000000, 9000000, 100, 10000, '진행중', :account_id)
    """), {"account_id": account["id"]})
    values = scenario_values(session_id=3, cycle_no=1)
    values["training_account_id"] = account["id"]
    scenario = repo.create_risk_scenario(values)
    repo.replace_risk_plan_steps(scenario["id"], [
        {
            "plan_group": "BUY", "plan_type": "ENTRY", "step_no": 1, "status": "EXECUTED",
            "trigger_type": "PRICE_LINE", "trigger_price": 10000, "trigger_text": "1차 매수",
            "planned_ratio_pct": None, "planned_quantity": None, "planned_amount": None,
            "memo": None, "executed_trade_id": None,
        },
        {
            "plan_group": "SELL", "plan_type": "TAKE_PROFIT", "step_no": 2, "status": "PLANNED",
            "trigger_type": "PRICE_LINE", "trigger_price": 11000, "trigger_text": "1차 익절",
            "planned_ratio_pct": None, "planned_quantity": None, "planned_amount": None,
            "memo": None, "executed_trade_id": None,
        },
        {
            "plan_group": "SELL", "plan_type": "FULL_STOP", "step_no": 3, "status": "PLANNED",
            "trigger_type": "PRICE_LINE", "trigger_price": 9000, "trigger_text": "전량 손절",
            "planned_ratio_pct": 100, "planned_quantity": None, "planned_amount": None,
            "memo": None, "executed_trade_id": None,
        },
    ])
    repo.activate_risk_scenario(scenario["id"], activation_values())
    db.commit()
    service = TradeTrainingService(db)
    service._current_price_row = lambda _session: {"close": 10000}

    detail = service.update_active_risk_scenario(
        scenario["id"],
        TradeTrainingRiskScenarioDraftRequest(
            profit_scenario_text="재지정 예정",
            stop_scenario_text="재지정 예정",
            buy_steps=[],
            sell_steps=[],
            change_reason="가격 초기화",
        ),
    )

    assert detail["scenario"]["status"] == "ACTIVE"
    assert detail["buy_steps"] == []
    assert detail["sell_steps"] == []
    stored_steps = repo.list_risk_plan_steps(scenario["id"])
    assert len(stored_steps) == 3
    assert all(bool(step["is_removed"]) for step in stored_steps)


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
