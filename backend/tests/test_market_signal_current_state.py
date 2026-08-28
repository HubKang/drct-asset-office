from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.app.services.market_signal_service import MarketSignalService


def _service() -> tuple[MarketSignalService, Session, dict[str, object]]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    session = Session(engine)
    session.execute(text("""
        CREATE TABLE market_signal_definitions (
            id INTEGER PRIMARY KEY,
            signal_code TEXT NOT NULL,
            signal_name TEXT NOT NULL,
            signal_type TEXT NOT NULL,
            status TEXT NOT NULL,
            current_version INTEGER NOT NULL
        )
    """))
    session.execute(text("""
        CREATE TABLE market_signal_current_states (
            signal_definition_id INTEGER PRIMARY KEY,
            signal_version_id INTEGER NOT NULL,
            previous_state TEXT,
            current_state TEXT NOT NULL,
            evaluated_at TEXT NOT NULL,
            effective_date TEXT,
            last_transition_at TEXT,
            last_transition_from TEXT,
            last_transition_to TEXT,
            evaluation_status TEXT NOT NULL,
            missing_reason TEXT,
            error_message TEXT,
            collection_run_id INTEGER,
            trigger_type TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """))
    session.execute(text("CREATE TABLE market_data_collection_policies (item_type TEXT, item_code TEXT, frequency TEXT)"))
    session.execute(text("CREATE TABLE market_index_daily_prices (index_code TEXT, price_date TEXT, close_price REAL)"))
    session.execute(text("CREATE TABLE market_indicator_values (indicator_code TEXT, value_date TEXT, value REAL, close_value REAL)"))
    session.execute(text("CREATE TABLE market_indicators (indicator_code TEXT, data_frequency TEXT)"))
    session.execute(text("""
        INSERT INTO market_signal_definitions
        (id, signal_code, signal_name, signal_type, status, current_version)
        VALUES (1, 'TEST_CURRENT', '현재 상태 테스트', 'COMPOSITE', 'ACTIVE', 3)
    """))
    session.commit()
    target: dict[str, object] = {
        "id": 1,
        "signal_code": "TEST_CURRENT",
        "signal_name": "현재 상태 테스트",
        "signal_type": "COMPOSITE",
        "category": "RATE",
        "trend_item_code": "BASE_RATE",
        "status": "ACTIVE",
        "current_version": 3,
    }
    service = MarketSignalService(session)
    service._current_evaluation_targets = lambda: [target]  # type: ignore[method-assign]
    return service, session, target


def _detail(state: str) -> dict[str, object]:
    return {
        "current_state": state,
        "effective_date": "2026-08-03",
        "score": 72.0,
        "evaluation_status": "SUCCESS",
        "required": {"satisfied": 1, "total": 1},
        "confirm": {"satisfied": 0, "total": 0},
        "opposing": {"satisfied": 0, "total": 0},
        "conditions": [],
        "missing_indicators": [],
        "missing_reason": None,
        "explanation": "현재 데이터로 계산한 상태",
    }


def test_current_evaluation_initializes_then_records_only_real_transition() -> None:
    service, session, _ = _service()
    current = _detail("LIVE")
    service._evaluate_current_target = lambda target: dict(current)  # type: ignore[method-assign]

    first = service.evaluate_current_signals(trigger_type="MANUAL")
    assert first["evaluated_count"] == 1
    assert first["transition_count"] == 0
    row = session.execute(text("SELECT * FROM market_signal_current_states WHERE signal_definition_id=1")).mappings().one()
    assert row["current_state"] == "LIVE"
    assert row["last_transition_at"] is None

    repeated = service.evaluate_current_signals(trigger_type="MANUAL")
    assert repeated["transition_count"] == 0
    current["current_state"] = "ACTIVE"
    changed = service.evaluate_current_signals(trigger_type="MARKET_DATA_COLLECTION", collection_run_id=91)
    assert changed["transition_count"] == 1
    transitioned = session.execute(text("SELECT * FROM market_signal_current_states WHERE signal_definition_id=1")).mappings().one()
    assert transitioned["previous_state"] == "LIVE"
    assert transitioned["current_state"] == "ACTIVE"
    assert transitioned["last_transition_from"] == "LIVE"
    assert transitioned["last_transition_to"] == "ACTIVE"
    transition_time = transitioned["last_transition_at"]

    unchanged = service.evaluate_current_signals(trigger_type="MANUAL")
    assert unchanged["transition_count"] == 0
    final_row = session.execute(text("SELECT * FROM market_signal_current_states WHERE signal_definition_id=1")).mappings().one()
    assert final_row["last_transition_at"] == transition_time
    assert final_row["collection_run_id"] is None


def test_today_transition_uses_kst_current_state_and_excludes_draft() -> None:
    service, session, _ = _service()
    current = _detail("LIVE")
    service._evaluate_current_target = lambda target: dict(current)  # type: ignore[method-assign]
    service.evaluate_current_signals()
    current["current_state"] = "ACTIVE"
    service.evaluate_current_signals()

    today = service.list_today_current_transitions()
    assert len(today["items"]) == 1
    assert today["items"][0]["from_state"] == "LIVE"
    assert today["items"][0]["to_state"] == "ACTIVE"
    assert today["items"][0]["conditions"] == []

    current_state = service.list_current_signal_states()
    assert current_state["items"][0]["category"] == "RATE"
    assert current_state["items"][0]["item_code"] == "BASE_RATE"
    assert current_state["items"][0]["from_state"] == "LIVE"
    assert current_state["items"][0]["to_state"] == "ACTIVE"
    assert current_state["items"][0]["last_transition_at"] is not None

    session.execute(text("UPDATE market_signal_definitions SET status='DRAFT' WHERE id=1"))
    session.commit()
    assert service.list_today_current_transitions()["items"] == []

def test_freshness_policy_marks_stale_monthly_value_only_after_45_days() -> None:
    service, session, _ = _service()
    session.execute(text("INSERT INTO market_data_collection_policies VALUES ('INDICATOR', 'MONTHLY_TEST', 'MONTHLY')"))
    session.execute(text("INSERT INTO market_indicators VALUES ('MONTHLY_TEST', 'MONTHLY')"))
    session.execute(
        text("INSERT INTO market_indicator_values VALUES ('MONTHLY_TEST', :value_date, 1, NULL)"),
        {"value_date": (date.today() - timedelta(days=46)).isoformat()},
    )
    session.commit()

    issue = service._freshness_issue("INDICATOR", "MONTHLY_TEST")
    assert issue is not None
    assert issue["allowed_age_days"] == 45
    assert issue["age_days"] == 46

    session.execute(
        text("INSERT INTO market_indicator_values VALUES ('MONTHLY_TEST', :value_date, 2, NULL)"),
        {"value_date": (date.today() - timedelta(days=45)).isoformat()},
    )
    session.commit()
    assert service._freshness_issue("INDICATOR", "MONTHLY_TEST") is None


def test_duplicate_run_is_rejected_while_evaluation_lock_is_held() -> None:
    from backend.app.services.market_signal_service import CURRENT_SIGNAL_EVALUATION_LOCK

    service, _, _ = _service()
    assert CURRENT_SIGNAL_EVALUATION_LOCK.acquire(blocking=False)
    try:
        result = service.evaluate_current_signals()
    finally:
        CURRENT_SIGNAL_EVALUATION_LOCK.release()
    assert result["status"] == "ALREADY_RUNNING"
    assert result["evaluated_count"] == 0
