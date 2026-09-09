from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

from backend.app.services.drct_insight_service import DrctInsightService


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    session = Session(engine)
    for statement in (
        "CREATE TABLE stock_daily_prices (stock_id INTEGER, trade_date TEXT, close_price REAL, change_rate REAL)",
        "CREATE TABLE market_theme_daily_returns (theme_id INTEGER, return_date TEXT, avg_change_rate REAL)",
        "CREATE TABLE chart_marker_events (id INTEGER, stock_id INTEGER, marker_date TEXT, review_result TEXT, reviewed_at TEXT)",
        """CREATE TABLE drct_insight_candidate_evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT, analysis_date TEXT, stock_id INTEGER, theme_id INTEGER,
            candidate_level TEXT, observation_rank INTEGER, success_similarity REAL, failure_similarity REAL,
            pattern_edge REAL, user_status TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, evaluated_at TEXT,
            focus_rank INTEGER, theme_gate TEXT, flow_gate TEXT, pattern_status TEXT, us_lead_status TEXT,
            insight_rule_version TEXT, d0_return REAL, d1_return REAL, d3_return REAL, d5_return REAL,
            mfe_5d REAL, mae_5d REAL, outcome_status TEXT DEFAULT 'PENDING', outcome_evaluated_at TEXT,
            UNIQUE(analysis_date, stock_id))""",
    ):
        session.execute(text(statement))
    session.commit()
    return session


def test_market_mode_uses_existing_kr_market_hours() -> None:
    assert DrctInsightService._market_mode(datetime(2026, 9, 7, 8, 59)) == "PRE_MARKET"
    assert DrctInsightService._market_mode(datetime(2026, 9, 7, 9, 0)) == "INTRADAY"
    assert DrctInsightService._market_mode(datetime(2026, 9, 7, 15, 30)) == "POST_MARKET"
    assert DrctInsightService._market_mode(datetime(2026, 9, 6, 12, 0)) == "POST_MARKET"


def test_batch_outcome_uses_daily_sources_and_marker_runtime_status() -> None:
    db = _session()
    db.execute(text("INSERT INTO stock_daily_prices VALUES (1,'2026-09-07',12000,4.5)"))
    db.execute(text("INSERT INTO market_theme_daily_returns VALUES (10,'2026-09-07',1.5)"))
    db.execute(text("INSERT INTO chart_marker_events VALUES (7,1,'2026-09-07','S','2026-09-07 18:00:00')"))
    db.commit()

    outcomes = DrctInsightService(db)._batch_outcomes("2026-09-07", [{"stock_id": 1, "theme_id": 10}, {"stock_id": 2, "theme_id": 10}])

    assert outcomes[1]["d0_return"] == 4.5
    assert outcomes[1]["relative_return"] == 3.0
    assert outcomes[1]["marker_status"] == "S"
    assert outcomes[2]["status"] == "NOT_READY"
    assert outcomes[2]["d0_return"] is None
    assert outcomes[2]["marker_status"] == "UNRECORDED"


def test_batch_outcome_uses_three_selects_instead_of_per_stock_queries() -> None:
    db = _session()
    statements: list[str] = []
    event.listen(db.bind, "before_cursor_execute", lambda _conn, _cursor, statement, _params, _context, _many: statements.append(statement))

    DrctInsightService(db)._batch_outcomes(
        "2026-09-07",
        [{"stock_id": stock_id, "theme_id": 10 + stock_id % 2} for stock_id in range(1, 21)],
    )

    assert len([statement for statement in statements if statement.lstrip().upper().startswith("SELECT")]) == 3


def test_review_queue_includes_non_focus_watch_and_prioritizes_triggered_loss() -> None:
    base = {
        "stock_code": "000001", "theme_id": 10, "theme_name": "테마", "candidate_level": "PRELIMINARY",
        "pattern_status": "PROMISING", "success_similarity": 88.0,
    }
    focus = {**base, "stock_id": 1, "stock_name": "Focus", "focus_candidate": True, "gates": {"execution": "WAIT"},
             "outcome": {"d0_return": 4.0, "relative_return": 2.0, "status": "READY", "marker_status": "UNRECORDED"}}
    watched = {**base, "stock_id": 2, "stock_name": "Watch", "focus_candidate": False, "gates": {"execution": "TRIGGERED"},
               "outcome": {"d0_return": -1.0, "relative_return": -2.0, "status": "READY", "marker_status": "UNRECORDED"}}

    queue = DrctInsightService._review_queue([focus, watched], {2})

    assert len(queue) == 2
    assert queue[0]["priority"] == "HIGH"
    assert {row["stock_id"] for row in queue} == {1, 2}
    assert "WEAK" in next(row for row in queue if row["stock_id"] == 2)["categories"]
    assert "STRONG" in next(row for row in queue if row["stock_id"] == 1)["categories"]


def test_ready_loss_and_missing_outcome_are_reviewed_without_auto_failure_marker() -> None:
    base = {
        "stock_code": "000001", "theme_id": 10, "theme_name": "테마", "candidate_level": "PRELIMINARY",
        "pattern_status": "PROMISING", "success_similarity": 88.0, "focus_candidate": False,
    }
    ready_loss = {**base, "stock_id": 1, "stock_name": "ReadyLoss", "gates": {"execution": "READY"},
                  "outcome": {"d0_return": -1.0, "relative_return": -2.0, "status": "READY", "marker_status": "UNRECORDED"}}
    missing = {**base, "stock_id": 2, "stock_name": "Missing", "gates": {"execution": "WAIT"},
               "outcome": {"d0_return": None, "relative_return": None, "status": "NOT_READY", "marker_status": "UNRECORDED"}}

    queue = DrctInsightService._review_queue([ready_loss, missing], {1, 2})

    assert next(row for row in queue if row["stock_id"] == 1)["priority"] == "HIGH"
    assert "OUTCOME_MISSING" in next(row for row in queue if row["stock_id"] == 2)["categories"]
    assert all(row["outcome"]["marker_status"] == "UNRECORDED" for row in queue)


def test_candidate_evaluation_upsert_is_duplicate_safe() -> None:
    db = _session()
    service = DrctInsightService(db)
    row = SimpleNamespace(
        stock_id=1, theme_id=10, final_candidate=False, observation_rank=1,
        success_similarity=88.0, failure_similarity=None, pattern_edge=None,
        gates=SimpleNamespace(execution="READY", theme="PASS", flow="WATCH"),
        focus_rank=1, pattern_status="PROMISING",
        us_lead=SimpleNamespace(linked=True, strength="STRONG"),
    )

    service._persist_candidate_rows("2026-09-07", [row])
    service._persist_candidate_rows("2026-09-07", [row])

    assert db.execute(text("SELECT COUNT(*) FROM drct_insight_candidate_evaluations")).scalar_one() == 1
    saved = db.execute(text("SELECT focus_rank, theme_gate, flow_gate, pattern_status, us_lead_status, insight_rule_version FROM drct_insight_candidate_evaluations")).mappings().one()
    assert dict(saved) == {"focus_rank": 1, "theme_gate": "PASS", "flow_gate": "WATCH", "pattern_status": "PROMISING", "us_lead_status": "STRONG", "insight_rule_version": "P3B_V1"}
