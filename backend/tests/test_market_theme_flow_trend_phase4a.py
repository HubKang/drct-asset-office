from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.services.market_theme_flow_trend_service import (
    MarketThemeFlowTrendService,
    invalidate_market_theme_flow_trend_cache,
)


@pytest.fixture()
def trend_db():
    invalidate_market_theme_flow_trend_cache()
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as conn:
        conn.exec_driver_sql("""CREATE TABLE market_themes (
            id INTEGER PRIMARY KEY, theme_name TEXT, parent_theme_id INTEGER,
            sort_order INTEGER, is_active INTEGER, theme_level TEXT
        )""")
        conn.exec_driver_sql("CREATE TABLE stocks (id INTEGER PRIMARY KEY, stock_code TEXT, stock_name TEXT, is_active INTEGER)")
        conn.exec_driver_sql("CREATE TABLE market_theme_stocks (id INTEGER PRIMARY KEY, theme_id INTEGER, stock_id INTEGER, is_active INTEGER)")
        conn.exec_driver_sql("""CREATE TABLE stock_investor_flows (
            id INTEGER PRIMARY KEY, stock_id INTEGER, flow_date TEXT,
            individual_net_amount INTEGER, foreign_net_amount INTEGER,
            institution_net_amount INTEGER, program_net_amount INTEGER
        )""")
        conn.exec_driver_sql("CREATE TABLE stock_daily_prices (id INTEGER PRIMARY KEY, stock_id INTEGER, trade_date TEXT, trading_value INTEGER)")
        conn.exec_driver_sql("""CREATE TABLE market_theme_stock_daily_returns (
            id INTEGER PRIMARY KEY, stock_id INTEGER, return_date TEXT, trading_value INTEGER
        )""")
        conn.exec_driver_sql("CREATE TABLE market_theme_daily_returns (id INTEGER PRIMARY KEY, theme_id INTEGER, return_date TEXT, avg_change_rate REAL)")
        conn.exec_driver_sql("""INSERT INTO market_themes VALUES
            (10,'그룹A',NULL,0,1,'THEME_GROUP'),
            (1,'AI반도체',10,1,1,'THEME'),(2,'전력기기',10,2,1,'THEME')""")
        conn.exec_driver_sql("INSERT INTO stocks VALUES (1,'000001','공유종목',1),(2,'000002','AI종목',1),(3,'000003','결측종목',1)")
        conn.exec_driver_sql("INSERT INTO market_theme_stocks VALUES (1,1,1,1),(2,2,1,1),(3,1,2,1),(4,2,3,1),(5,1,1,1)")
        dates = [f"2026-07-{day:02d}" for day in range(1, 7)]
        row_id = 1
        for index, day in enumerate(dates):
            # shared stock: foreign positive; institution alternates only on first day.
            institution = 40 if index != 3 else None
            conn.exec_driver_sql(
                "INSERT INTO stock_investor_flows VALUES (?,?,?,?,?,?,?)",
                (row_id, 1, day, -140, 100, institution, 30),
            )
            conn.exec_driver_sql("INSERT INTO stock_daily_prices VALUES (?,?,?,?)", (row_id, 1, day, 1))
            conn.exec_driver_sql("INSERT INTO market_theme_stock_daily_returns VALUES (?,?,?,?)", (row_id, 1, day, 1000))
            row_id += 1
            foreign = 0 if index == 2 else (-200 if index == 3 else 200)
            conn.exec_driver_sql(
                "INSERT INTO stock_investor_flows VALUES (?,?,?,?,?,?,?)",
                (row_id, 2, day, -80, foreign, 20, -10),
            )
            conn.exec_driver_sql("INSERT INTO stock_daily_prices VALUES (?,?,?,?)", (row_id, 2, day, 1))
            conn.exec_driver_sql("INSERT INTO market_theme_stock_daily_returns VALUES (?,?,?,?)", (row_id, 2, day, 2000))
            row_id += 1
            conn.exec_driver_sql("INSERT INTO market_theme_daily_returns VALUES (?,?,?,?)", (row_id, 1, day, index + 0.5))
            conn.exec_driver_sql("INSERT INTO market_theme_daily_returns VALUES (?,?,?,?)", (row_id + 1, 2, day, -(index + 0.5)))
            row_id += 2
    Session = sessionmaker(bind=engine)
    with Session() as session:
        yield session, engine


def get_theme(result, theme_id: int):
    return next(theme for theme in result.themes if theme.theme_id == theme_id)


def test_full_and_fractional_apply_same_factor_to_amount_and_trading(trend_db) -> None:
    session, _ = trend_db
    service = MarketThemeFlowTrendService(session)
    full = get_theme(service.get_trend(end_date="2026-07-06", actor="FOREIGN", attribution="FULL", limit=None, refresh=True), 1).cells[-1]
    fractional = get_theme(service.get_trend(end_date="2026-07-06", actor="FOREIGN", attribution="FRACTIONAL", limit=None, refresh=True), 1).cells[-1]

    assert full.net_buy_amount == 300
    assert full.trading_value == 3000
    assert fractional.net_buy_amount == 250  # shared 100/2 + unique 200
    assert fractional.trading_value == 2500  # shared 1000/2 + unique 2000
    assert full.flow_strength == fractional.flow_strength == 10.0


@pytest.mark.parametrize(
    ("actor", "expected"),
    [("INDIVIDUAL", -220), ("FOREIGN", 300), ("INSTITUTION", 60), ("FOREIGN_INSTITUTION", 360), ("PROGRAM", 20)],
)
def test_actor_aggregation_and_program_is_separate(trend_db, actor: str, expected: int) -> None:
    session, _ = trend_db
    cell = get_theme(MarketThemeFlowTrendService(session).get_trend(
        end_date="2026-07-06", actor=actor, attribution="FULL", limit=None, refresh=True
    ), 1).cells[-1]
    assert cell.net_buy_amount == expected


def test_breadth_zero_null_completeness_and_contributors(trend_db) -> None:
    session, _ = trend_db
    result = MarketThemeFlowTrendService(session).get_trend(
        end_date="2026-07-03", actor="FOREIGN", metric="BREADTH", attribution="FULL", limit=None, refresh=True
    )
    ai = get_theme(result, 1).cells[-1]
    power = get_theme(result, 2).cells[-1]
    assert ai.net_buy_amount == 100  # actual zero remains data
    assert ai.actor_data_stock_count == 2
    assert ai.zero_stock_count == 1
    assert ai.breadth_ratio == 50.0
    assert len(ai.top_contributors) == 2
    assert power.actor_data_stock_count == 1
    assert power.connected_stock_count == 2
    assert power.missing_stock_count == 1
    assert power.data_quality == "INSUFFICIENT"
    assert power.completeness_ratio == 0.5


def test_period_summary_streak_top_cards_filters_and_limit(trend_db) -> None:
    session, _ = trend_db
    result = MarketThemeFlowTrendService(session).get_trend(
        end_date="2026-07-06", recent_days=6, actor="FOREIGN", metric="NET_AMOUNT",
        attribution="FULL", theme_group_id=10, search="AI", limit=1, refresh=True,
    )
    assert result.dates == [f"2026-07-{day:02d}" for day in range(1, 7)]
    assert len(result.themes) == 1
    theme = result.themes[0]
    assert theme.theme_id == 1
    assert theme.twenty_day_summary.cumulative_net_buy_amount == 1200
    assert theme.twenty_day_summary.cumulative_trading_value == 18000
    assert theme.twenty_day_summary.flow_strength == pytest.approx(6.6667)
    assert theme.twenty_day_summary.current_streak == 2  # latest two positive after negative day
    assert result.summary.top_today is not None
    assert result.summary.top_five_day is not None
    assert result.summary.top_breadth is not None
    assert result.summary.top_streak is not None


def test_missing_breaks_streak_and_foreign_institution_requires_both(trend_db) -> None:
    session, _ = trend_db
    combo = get_theme(MarketThemeFlowTrendService(session).get_trend(
        end_date="2026-07-04", recent_days=4, actor="FOREIGN_INSTITUTION",
        attribution="FULL", limit=None, refresh=True,
    ), 2)
    missing_day = combo.cells[-1]
    assert missing_day.net_buy_amount is None
    assert combo.twenty_day_summary.current_streak == 0


def test_validation_cache_query_bound_and_openapi(trend_db) -> None:
    session, engine = trend_db
    service = MarketThemeFlowTrendService(session)
    count = 0

    def before_cursor_execute(*_args):
        nonlocal count
        count += 1

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    cold = service.get_trend(end_date="2026-07-06", limit=None, refresh=True)
    assert count == 4
    count = 0
    warm = service.get_trend(end_date="2026-07-06", limit=None)
    assert count == 0
    assert cold.performance["cache_hit"] is False
    assert warm.performance["cache_hit"] is True
    assert warm.performance["query_count"] == 0
    assert warm.performance["query_ms"] == 0.0
    assert warm.performance["calculation_ms"] == 0.0
    assert warm.performance["serialization_ms"] == 0.0
    assert cold.performance["serialization_ms"] >= 0.0
    event.remove(engine, "before_cursor_execute", before_cursor_execute)

    for kwargs in ({"actor": "OTHER"}, {"metric": "SCORE"}, {"attribution": "PAST"}):
        with pytest.raises(HTTPException) as invalid:
            service.get_trend(end_date="2026-07-06", **kwargs)
        assert invalid.value.status_code == 400
    path = "/external/kiwoom/market-themes/flow-trend"
    operation = app.openapi()["paths"][path]["get"]
    assert set(app.openapi()["paths"][path]) == {"get"}
    limit_parameter = next(item for item in operation["parameters"] if item["name"] == "limit")
    assert "default" not in limit_parameter["schema"]
