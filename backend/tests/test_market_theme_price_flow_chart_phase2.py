from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.app.services.market_theme_price_flow_chart_service import MarketThemePriceFlowChartService
from backend.app.main import app


@pytest.fixture()
def chart_db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            """CREATE TABLE stocks (
                id INTEGER PRIMARY KEY, stock_code TEXT NOT NULL UNIQUE, stock_name TEXT NOT NULL,
                market TEXT, sector TEXT, industry TEXT, isin_code TEXT, corp_name TEXT,
                corp_reg_no TEXT, last_synced_at TEXT, source TEXT, security_type TEXT,
                is_active INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )"""
        )
        conn.exec_driver_sql(
            """CREATE TABLE stock_daily_prices (
                id INTEGER PRIMARY KEY, stock_id INTEGER NOT NULL, trade_date TEXT NOT NULL,
                close_price REAL, change_rate REAL
            )"""
        )
        conn.exec_driver_sql(
            """CREATE TABLE stock_investor_flows (
                id INTEGER PRIMARY KEY, stock_id INTEGER NOT NULL, flow_date TEXT NOT NULL,
                individual_net_qty INTEGER, individual_net_amount INTEGER,
                foreign_net_qty INTEGER, foreign_net_amount INTEGER,
                institution_net_qty INTEGER, institution_net_amount INTEGER,
                program_net_qty INTEGER, program_net_amount INTEGER
            )"""
        )
        conn.exec_driver_sql("CREATE TABLE market_themes (id INTEGER PRIMARY KEY, theme_name TEXT)")
        conn.exec_driver_sql(
            """CREATE TABLE market_trend_events (
                id INTEGER PRIMARY KEY, stock_id INTEGER, trade_date TEXT, theme_id INTEGER,
                user_memo TEXT, is_active INTEGER, deleted_at TEXT
            )"""
        )
        conn.exec_driver_sql(
            """CREATE TABLE market_trend_event_theme_links (
                id INTEGER PRIMARY KEY, event_id INTEGER, market_theme_id INTEGER,
                is_active INTEGER, deleted_at TEXT
            )"""
        )
        conn.execute(text(
            """INSERT INTO stocks (
                id, stock_code, stock_name, market, is_active, created_at, updated_at
            ) VALUES (1, '000001', '테스트종목', 'KOSPI', 1, '2026-01-01', '2026-01-01'),
                     (2, '000002', '빈종목', 'KOSDAQ', 1, '2026-01-01', '2026-01-01')"""
        ))
        start = date(2026, 1, 1)
        for index in range(70):
            day = (start + timedelta(days=index)).isoformat()
            conn.execute(
                text("INSERT INTO stock_daily_prices VALUES (:id, 1, :day, :close, :rate)"),
                {"id": index + 1, "day": day, "close": 100 + index, "rate": index / 10},
            )
            # One missing day verifies that the visible series breaks while the next sum continues.
            missing = index == 60
            conn.execute(
                text(
                    """INSERT INTO stock_investor_flows VALUES (
                        :id, 1, :day, :individual_qty, :individual_amount,
                        :foreign_qty, :foreign_amount, :institution_qty, :institution_amount,
                        :program_qty, :program_amount
                    )"""
                ),
                {
                    "id": index + 1,
                    "day": day,
                    "individual_qty": None if missing else index + 1,
                    "individual_amount": None if missing else (index + 1) * 1_000_000,
                    "foreign_qty": None if missing else -(index + 1),
                    "foreign_amount": None if missing else -(index + 1) * 2_000_000,
                    "institution_qty": None if missing else 2,
                    "institution_amount": None if missing else 3_000_000,
                    "program_qty": None if missing else 3,
                    "program_amount": None if missing else 4_000_000,
                },
            )
        conn.exec_driver_sql("INSERT INTO market_themes VALUES (10, '현재테마'), (11, '다른테마')")
        conn.exec_driver_sql(
            """INSERT INTO market_trend_events VALUES
               (1, 1, '2026-03-05', NULL, '첫 메모', 1, NULL),
               (2, 1, '2026-03-05', 11, '둘째 메모', 1, NULL)"""
        )
        conn.exec_driver_sql(
            "INSERT INTO market_trend_event_theme_links VALUES (1, 1, 10, 1, NULL)"
        )
    Session = sessionmaker(bind=engine)
    with Session() as session:
        yield session


def test_periods_use_saved_trading_day_counts(chart_db) -> None:
    service = MarketThemePriceFlowChartService(chart_db)
    one = service.get_chart(1, period="1M", unit="QUANTITY", view="ACTUAL")
    three = service.get_chart(1, period="3M", unit="QUANTITY", view="ACTUAL", theme_id=10)
    six = service.get_chart(1, period="6M", unit="QUANTITY", view="ACTUAL")

    assert len(one.series) == 20
    assert len(three.series) == 63
    assert len(six.series) == 70
    assert six.period.requested_trading_days == 126
    assert six.period.actual_trading_days == 70


def test_cumulative_quantity_restarts_and_preserves_state_across_null(chart_db) -> None:
    result = MarketThemePriceFlowChartService(chart_db).get_chart(
        1, period="1M", unit="QUANTITY", view="ACTUAL"
    )
    assert result.series[0].individual_cumulative == 51
    missing = next(item for item in result.series if item.individual_daily is None)
    assert missing.individual_cumulative is None
    after = result.series[result.series.index(missing) + 1]
    expected = sum(range(51, 61)) + 62
    assert after.individual_cumulative == expected
    assert result.summary.program_cumulative == 57  # 19 valid days, program is not added to investors.


def test_amount_and_normalization_are_independent_and_bounded(chart_db) -> None:
    amount = MarketThemePriceFlowChartService(chart_db).get_chart(
        1, period="1M", unit="AMOUNT", view="NORMALIZED"
    )
    assert amount.series[0].individual_daily == 51_000_000
    for field in (
        "normalized_price", "normalized_individual", "normalized_foreign",
        "normalized_institution", "normalized_program",
    ):
        values = [getattr(item, field) for item in amount.series if getattr(item, field) is not None]
        assert values
        assert max(abs(value) for value in values) <= 100
        assert max(abs(value) for value in values) == 100


def test_events_are_grouped_by_date_and_current_theme_is_highlighted(chart_db) -> None:
    result = MarketThemePriceFlowChartService(chart_db).get_chart(
        1, period="3M", unit="QUANTITY", view="ACTUAL", theme_id=10
    )
    assert len(result.events) == 1
    event = result.events[0]
    assert event.event_count == 2
    assert event.is_current_theme is True
    assert any(item.is_current_theme and item.theme_name == "현재테마" for item in event.items)


def test_empty_stock_and_invalid_parameters(chart_db) -> None:
    empty = MarketThemePriceFlowChartService(chart_db).get_chart(
        2, period="3M", unit="QUANTITY", view="ACTUAL"
    )
    assert empty.data_quality.status == "EMPTY"
    assert empty.series == []

    with pytest.raises(HTTPException) as invalid:
        MarketThemePriceFlowChartService(chart_db).get_chart(
            1, period="2M", unit="QUANTITY", view="ACTUAL"
        )
    assert invalid.value.status_code == 400

    with pytest.raises(HTTPException) as missing:
        MarketThemePriceFlowChartService(chart_db).get_chart(
            999, period="3M", unit="QUANTITY", view="ACTUAL"
        )
    assert missing.value.status_code == 404


def test_zero_normalization_never_returns_nan() -> None:
    assert MarketThemePriceFlowChartService._normalized([0, 0, None]) == [0.0, 0.0, None]


def test_streak_requires_a_valid_latest_direction() -> None:
    assert MarketThemePriceFlowChartService._streak([1, 2, 3]) == 3
    assert MarketThemePriceFlowChartService._streak([-1, -2]) == -2
    assert MarketThemePriceFlowChartService._streak([1, 2, None]) == 0
    assert MarketThemePriceFlowChartService._streak([-1, 0]) == 0


def test_latest_date_mismatch_uses_common_end_date(chart_db) -> None:
    chart_db.execute(text(
        "INSERT INTO stock_daily_prices VALUES (999, 1, '2026-04-01', 200, 1.0)"
    ))
    result = MarketThemePriceFlowChartService(chart_db).get_chart(
        1, period="1M", unit="QUANTITY", view="ACTUAL"
    )
    assert result.latest_dates.price == "2026-04-01"
    assert result.latest_dates.common == "2026-03-11"
    assert result.period.end_date == "2026-03-11"
    assert result.data_quality.status == "LATEST_MISMATCH"


def test_openapi_exposes_read_only_chart_route() -> None:
    path = "/external/kiwoom/market-themes/stocks/{stock_id}/price-flow-chart"
    operation = app.openapi()["paths"][path]
    assert set(operation) == {"get"}
