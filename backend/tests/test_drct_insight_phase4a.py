from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.app.services.drct_future_outcome_service import FutureOutcomeService
from backend.app.services.drct_insight_performance_service import DrctInsightPerformanceService


def _session() -> Session:
    db = Session(create_engine("sqlite:///:memory:"))
    for statement in (
        "CREATE TABLE stocks (id INTEGER PRIMARY KEY, stock_code TEXT, stock_name TEXT)",
        "CREATE TABLE market_themes (id INTEGER PRIMARY KEY, theme_name TEXT)",
        "CREATE TABLE chart_marker_events (id INTEGER PRIMARY KEY, stock_id INTEGER, marker_date TEXT, review_result TEXT, reviewed_at TEXT)",
        """CREATE TABLE stock_daily_prices (
            stock_id INTEGER, trade_date TEXT, high_price REAL, low_price REAL,
            close_price REAL, change_rate REAL)""",
        """CREATE TABLE drct_insight_candidate_evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT, analysis_date TEXT, stock_id INTEGER, theme_id INTEGER,
            candidate_level TEXT, observation_rank INTEGER, success_similarity REAL, failure_similarity REAL,
            pattern_edge REAL, user_status TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, evaluated_at TEXT,
            focus_rank INTEGER, theme_gate TEXT, flow_gate TEXT, pattern_status TEXT, us_lead_status TEXT,
            insight_rule_version TEXT, d0_return REAL, d1_return REAL, d3_return REAL, d5_return REAL,
            mfe_5d REAL, mae_5d REAL, outcome_status TEXT DEFAULT 'PENDING', outcome_evaluated_at TEXT,
            UNIQUE(analysis_date, stock_id))""",
    ):
        db.execute(text(statement))
    db.execute(text("INSERT INTO stocks VALUES (1,'000001','테스트종목')"))
    db.execute(text("INSERT INTO market_themes VALUES (10,'테스트테마')"))
    db.commit()
    return db


def _candidate(db: Session, status: str = "PENDING") -> None:
    db.execute(text("""
        INSERT INTO drct_insight_candidate_evaluations
        (analysis_date,stock_id,theme_id,candidate_level,observation_rank,success_similarity,user_status,
         focus_rank,theme_gate,flow_gate,pattern_status,us_lead_status,insight_rule_version,outcome_status)
        VALUES ('2026-09-04',1,10,'FOCUS',2,72,'READY',1,'PASS','PASS','PROMISING','STRONG','P3B_V1',:status)
    """), {"status": status})
    db.commit()


def _price(db: Session, trade_date: str, close: float, high: float | None = None, low: float | None = None, change: float | None = None) -> None:
    db.execute(text("INSERT INTO stock_daily_prices VALUES (1,:date,:high,:low,:close,:change)"), {
        "date": trade_date, "high": high if high is not None else close,
        "low": low if low is not None else close, "close": close, "change": change,
    })


def test_horizon_calculator_uses_actual_trading_rows_and_completed_window() -> None:
    rows = [
        {"trade_date": "2026-09-07", "close_price": 102, "high_price": 104, "low_price": 99},
        {"trade_date": "2026-09-08", "close_price": 101, "high_price": 103, "low_price": 98},
        {"trade_date": "2026-09-09", "close_price": 106, "high_price": 108, "low_price": 100},
        {"trade_date": "2026-09-10", "close_price": 104, "high_price": 107, "low_price": 97},
        {"trade_date": "2026-09-11", "close_price": 110, "high_price": 115, "low_price": 101},
    ]
    outcome = FutureOutcomeService.calculate_horizons(100, rows, (1, 3, 5), 5)
    assert outcome == pytest.approx({"d1_return": 2, "d3_return": 6, "d5_return": 10, "mfe_5": 15, "mae_5": -3})
    partial = FutureOutcomeService.calculate_horizons(100, rows[:3], (1, 3, 5), 5)
    assert partial["d1_return"] == pytest.approx(2) and partial["d3_return"] == pytest.approx(6)
    assert partial["d5_return"] is None and partial["mfe_5"] is None and partial["mae_5"] is None


def test_refresh_progresses_pending_partial_complete_without_calendar_math() -> None:
    db = _session(); _candidate(db)
    _price(db, "2026-09-04", 100, change=4)
    _price(db, "2026-09-07", 102)
    db.commit()
    result = DrctInsightPerformanceService(db).refresh()
    row = db.execute(text("SELECT * FROM drct_insight_candidate_evaluations")).mappings().one()
    assert result.updated_count == 1 and row["outcome_status"] == "PARTIAL"
    assert row["d0_return"] == 4 and row["d1_return"] == 2 and row["d3_return"] is None

    for offset, close in enumerate((101, 106, 104, 110), start=1):
        _price(db, (date(2026, 9, 7) + timedelta(days=offset)).isoformat(), close, high=close + 5, low=close - 3)
    db.commit()
    DrctInsightPerformanceService(db).refresh()
    complete = db.execute(text("SELECT * FROM drct_insight_candidate_evaluations")).mappings().one()
    assert complete["outcome_status"] == "COMPLETE"
    assert complete["d3_return"] == pytest.approx(6) and complete["d5_return"] == pytest.approx(10)
    assert complete["mfe_5d"] == pytest.approx(15) and complete["mae_5d"] == pytest.approx(-2)
    assert DrctInsightPerformanceService(db).refresh().target_count == 0


def test_missing_d0_stays_pending_and_is_not_zero() -> None:
    db = _session(); _candidate(db)
    DrctInsightPerformanceService(db).refresh()
    row = db.execute(text("SELECT d0_return,d1_return,outcome_status FROM drct_insight_candidate_evaluations")).one()
    assert row == (None, None, "PENDING")


def test_evaluations_join_marker_filter_paginate_and_report_small_samples() -> None:
    db = _session(); _candidate(db, "COMPLETE")
    db.execute(text("""UPDATE drct_insight_candidate_evaluations
        SET d0_return=4,d1_return=2,d3_return=6,d5_return=10,mfe_5d=15,mae_5d=-3
    """))
    db.execute(text("INSERT INTO chart_marker_events VALUES (7,1,'2026-09-04','S','2026-09-05 10:00:00')"))
    _price(db, "2026-09-04", 100, change=4); db.commit()

    response = DrctInsightPerformanceService(db).evaluations(
        period="ALL", candidate_level="FOCUS", theme_id=10, pattern_status="PROMISING",
        outcome_status="COMPLETE", page=1, page_size=20,
    )

    assert response.total == 1 and response.total_pages == 1
    assert response.items[0].marker_status == "S" and response.items[0].focus_rank == 1
    assert response.summary.d5.mean == 10 and response.summary.d5.positive_ratio == 100
    assert response.groups["flow"][0].sample_status == "INSUFFICIENT"
    assert response.groups["pattern_edge"][0].sample_status == "ACCUMULATING"


def test_evaluations_sort_completed_outcomes_before_pending_without_zero_fallback() -> None:
    db = _session()
    for stock_id, name in ((2, "MFE우선"), (3, "D5우선"), (4, "D1우선"), (5, "D0우선")):
        db.execute(text("INSERT INTO stocks VALUES (:id,:code,:name)"), {
            "id": stock_id, "code": f"{stock_id:06d}", "name": name,
        })
        db.execute(text("""
            INSERT INTO drct_insight_candidate_evaluations
            (analysis_date,stock_id,theme_id,candidate_level,focus_rank,d0_return,d1_return,d3_return,d5_return,mfe_5d,outcome_status)
            VALUES ('2026-09-04',:stock_id,10,'FOCUS',:stock_id,:d0,:d1,:d3,:d5,:mfe,:status)
        """), {
            "stock_id": stock_id,
            "d0": {2: 1, 3: 8, 4: 10, 5: 20}[stock_id],
            "d1": {2: 1, 3: 8, 4: 10, 5: None}[stock_id],
            "d3": {2: 1, 3: 8, 4: None, 5: None}[stock_id],
            "d5": {2: 5, 3: 9, 4: None, 5: None}[stock_id],
            "mfe": {2: 12, 3: 10, 4: None, 5: None}[stock_id],
            "status": "COMPLETE" if stock_id in {2, 3} else "PARTIAL" if stock_id == 4 else "PENDING",
        })
    db.commit()

    response = DrctInsightPerformanceService(db).evaluations(period="ALL", page=1, page_size=20)

    assert [item.stock_id for item in response.items] == [2, 3, 4, 5]


def test_evaluations_sort_d0_desc_when_future_outcomes_are_all_pending() -> None:
    db = _session()
    for stock_id, d0 in ((2, 1.53), (3, 5.68), (4, 2.78)):
        db.execute(text("INSERT INTO stocks VALUES (:id,:code,:name)"), {
            "id": stock_id, "code": f"{stock_id:06d}", "name": f"종목{stock_id}",
        })
        db.execute(text("""
            INSERT INTO drct_insight_candidate_evaluations
            (analysis_date,stock_id,theme_id,candidate_level,focus_rank,d0_return,outcome_status)
            VALUES ('2026-09-04',:stock_id,10,'FOCUS',:stock_id,:d0,'PENDING')
        """), {"stock_id": stock_id, "d0": d0})
    db.commit()

    response = DrctInsightPerformanceService(db).evaluations(period="ALL", page=1, page_size=20)

    assert [item.d0_return for item in response.items] == [5.68, 2.78, 1.53]
