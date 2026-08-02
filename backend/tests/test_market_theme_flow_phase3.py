from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.services.market_theme_flow_analysis_service import MarketThemeFlowAnalysisService


@pytest.fixture()
def flow_db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE market_themes (id INTEGER PRIMARY KEY, theme_name TEXT NOT NULL)")
        conn.exec_driver_sql("CREATE TABLE stocks (id INTEGER PRIMARY KEY, stock_name TEXT, is_active INTEGER)")
        conn.exec_driver_sql("CREATE TABLE market_theme_stocks (id INTEGER PRIMARY KEY, theme_id INTEGER, stock_id INTEGER, is_active INTEGER)")
        conn.exec_driver_sql("""CREATE TABLE market_theme_daily_returns (
            id INTEGER PRIMARY KEY, theme_id INTEGER, return_date TEXT,
            avg_change_rate REAL, total_trading_value INTEGER
        )""")
        conn.exec_driver_sql("""CREATE TABLE market_theme_stock_daily_returns (
            id INTEGER PRIMARY KEY, theme_id INTEGER, stock_id INTEGER,
            return_date TEXT, trading_value INTEGER
        )""")
        conn.exec_driver_sql("""CREATE TABLE stock_daily_prices (
            id INTEGER PRIMARY KEY, stock_id INTEGER, trade_date TEXT, trading_value INTEGER
        )""")
        conn.exec_driver_sql("""CREATE TABLE stock_investor_flows (
            id INTEGER PRIMARY KEY, stock_id INTEGER, flow_date TEXT,
            individual_net_amount INTEGER, foreign_net_amount INTEGER,
            institution_net_amount INTEGER, program_net_amount INTEGER
        )""")
        conn.exec_driver_sql("INSERT INTO market_themes VALUES (1, '반도체'), (2, '빈 테마')")
        conn.exec_driver_sql("INSERT INTO stocks VALUES (1, 'A', 1), (2, 'B', 1)")
        conn.exec_driver_sql("INSERT INTO market_theme_stocks VALUES (1,1,1,1), (2,1,2,1)")
        conn.exec_driver_sql("""INSERT INTO market_theme_daily_returns VALUES
            (1,1,'2026-07-29',10,3000), (2,1,'2026-07-30',-5,3200), (3,1,'2026-07-31',2,3400)""")
        conn.exec_driver_sql("""INSERT INTO stock_daily_prices VALUES
            (1,1,'2026-07-29',1000),(2,2,'2026-07-29',2000),
            (3,1,'2026-07-30',1100),(4,2,'2026-07-30',2100),
            (5,1,'2026-07-31',1200),(6,2,'2026-07-31',2200)""")
        conn.exec_driver_sql("""INSERT INTO stock_investor_flows VALUES
            (1,1,'2026-07-29',100,200,300,400),(2,2,'2026-07-29',-50,100,-100,50),
            (3,1,'2026-07-30',10,-20,30,40),(4,2,'2026-07-30',20,-30,40,50),
            (5,1,'2026-07-31',1,120,240,60),(6,2,'2026-07-31',-1,-20,-40,NULL)""")
    Session = sessionmaker(bind=engine)
    with Session() as session:
        yield session, engine


def test_stock_and_theme_daily_summary_preserves_missing_values(flow_db) -> None:
    session, _ = flow_db
    theme, stocks = MarketThemeFlowAnalysisService(session).get_daily_context(1, "2026-07-31")

    assert stocks[1]["foreign_flow_strength"] == 10.0
    assert stocks[1]["summary_code"] == "FOREIGN_INSTITUTION_BUY"
    assert stocks[2]["program_net_amount"] is None
    assert stocks[2]["program_flow_strength"] is None
    assert theme["program"]["net_amount"] == 60  # missing program is not coerced to zero
    assert theme["program"]["data_stock_count"] == 1
    assert theme["connected_stock_count"] == 2
    assert theme["complete_stock_count"] == 1
    assert theme["quality_status"] == "INSUFFICIENT"


def test_neutral_threshold_and_quality_boundaries() -> None:
    service = MarketThemeFlowAnalysisService
    assert service._direction(0.0999) == 0
    assert service._direction(-0.0999) == 0
    assert service._direction(0.1) == 1
    assert service._quality(10, 9)[0] == "ENOUGH"
    assert service._quality(10, 6)[0] == "PARTIAL"
    assert service._quality(10, 5)[0] == "INSUFFICIENT"
    assert service._quality(10, 0)[0] == "EMPTY"


def test_theme_chart_compounds_return_and_keeps_program_separate(flow_db) -> None:
    session, _ = flow_db
    result = MarketThemeFlowAnalysisService(session).get_chart(
        1, period="3M", focus_date="2026-07-30"
    )

    assert result.period.requested_trading_days == 63
    assert result.period.actual_trading_days == 3
    assert result.common_latest_date == "2026-07-31"
    assert result.series[-1].theme_cumulative_return_pct == pytest.approx(6.59)
    assert result.summary.individual.cumulative_amount == 80
    assert result.summary.program.cumulative_amount == 600
    assert result.summary.individual.data_stock_count == 2
    assert result.summary.foreign.data_stock_count == 2
    assert result.summary.institution.data_stock_count == 2
    assert result.summary.program.data_stock_count == 1
    assert result.selected is not None
    assert result.selected.trade_date == "2026-07-30"
    assert result.series[-1].program_data_stock_count == 1
    assert result.data_quality == "INSUFFICIENT"


def test_daily_context_is_single_query_and_chart_is_bounded(flow_db) -> None:
    session, engine = flow_db
    count = 0

    def before_cursor_execute(*_args):
        nonlocal count
        count += 1

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    MarketThemeFlowAnalysisService(session).get_daily_context(1, "2026-07-31")
    assert count == 1
    count = 0
    MarketThemeFlowAnalysisService(session).get_chart(1, period="1M")
    assert count <= 5
    event.remove(engine, "before_cursor_execute", before_cursor_execute)


def test_empty_invalid_missing_and_openapi(flow_db) -> None:
    session, _ = flow_db
    empty = MarketThemeFlowAnalysisService(session).get_chart(2, period="1M")
    assert empty.series == []
    assert empty.data_quality == "EMPTY"
    with pytest.raises(HTTPException) as invalid:
        MarketThemeFlowAnalysisService(session).get_chart(1, period="2M")
    assert invalid.value.status_code == 400
    with pytest.raises(HTTPException) as missing:
        MarketThemeFlowAnalysisService(session).get_chart(999, period="1M")
    assert missing.value.status_code == 404

    path = "/external/kiwoom/market-themes/{theme_id}/price-flow-chart"
    assert set(app.openapi()["paths"][path]) == {"get"}
