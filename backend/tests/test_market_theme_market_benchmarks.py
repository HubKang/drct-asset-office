from datetime import date

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.app.services.external_kiwoom_service import ExternalKiwoomService


def test_market_benchmark_series_uses_saved_index_closes_for_rolling_30d_return() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE market_index_daily_prices (
                index_code TEXT NOT NULL,
                price_date TEXT NOT NULL,
                close_price REAL,
                change_rate REAL
            )
            """
        )
        connection.execute(
            text(
                """
                INSERT INTO market_index_daily_prices (index_code, price_date, close_price, change_rate)
                VALUES
                  ('KOSPI', '2026-09-26', 100, NULL),
                  ('KOSPI', '2026-10-01', 101, NULL),
                  ('KOSPI', '2026-10-20', 103, NULL),
                  ('KOSPI', '2026-10-26', 102, NULL)
                """
            )
        )

    with Session(engine) as db:
        series = ExternalKiwoomService(db)._get_market_benchmark_series(
            display_start=date(2026, 10, 1),
            calculation_start=date(2026, 9, 27),
            end=date(2026, 10, 26),
        )

    kospi = next(item for item in series if item.index_code == "KOSPI")
    assert [item.return_date for item in kospi.daily_returns] == ["2026-10-01", "2026-10-20", "2026-10-26"]
    assert kospi.daily_returns[0].daily_change_rate == pytest.approx(1.0)
    assert kospi.daily_returns[0].period_cumulative_change_rate == pytest.approx(0.0)
    assert kospi.daily_returns[-1].rolling_30d_change_rate == pytest.approx(2.0093)
    assert kospi.daily_returns[-1].rolling_period_change_rate == pytest.approx(2.0093)
    assert kospi.daily_returns[-1].period_cumulative_change_rate == pytest.approx(0.9901)
    assert next(item for item in series if item.index_code == "KOSDAQ").daily_returns == []


def test_market_benchmark_series_supports_90_day_rolling_return() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE market_index_daily_prices (
                index_code TEXT NOT NULL,
                price_date TEXT NOT NULL,
                close_price REAL,
                change_rate REAL
            )
            """
        )
        connection.execute(
            text(
                """
                INSERT INTO market_index_daily_prices (index_code, price_date, close_price, change_rate)
                VALUES
                  ('KOSPI', '2026-07-31', 100, NULL),
                  ('KOSPI', '2026-08-01', 110, NULL),
                  ('KOSPI', '2026-09-01', 121, NULL),
                  ('KOSPI', '2026-10-01', 133.1, NULL)
                """
            )
        )

    with Session(engine) as db:
        series = ExternalKiwoomService(db)._get_market_benchmark_series(
            display_start=date(2026, 10, 1),
            calculation_start=date(2026, 8, 1),
            end=date(2026, 10, 1),
            rolling_period_days=90,
        )

    kospi = next(item for item in series if item.index_code == "KOSPI")
    assert kospi.daily_returns[0].rolling_30d_change_rate == pytest.approx(10.0)
    assert kospi.daily_returns[0].rolling_period_change_rate == pytest.approx(30.0)
    assert kospi.daily_returns[0].period_cumulative_change_rate == pytest.approx(0.0)
