from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.app.entities.stock_daily_technical_indicator import StockDailyTechnicalIndicator
from backend.app.repositories.technical_indicator_repository import TechnicalIndicatorRepository
from backend.app.schemas.stock_price_schema import StockDailyPriceResponse


def _indicator_row(*, rsi14: float) -> dict[str, object]:
    return {
        "trade_date": "2026-08-25",
        "rsi14": rsi14,
        "macd": None,
        "macd_signal": None,
        "macd_histogram": None,
        "bb_upper": 110.0,
        "bb_middle": 100.0,
        "bb_lower": 90.0,
        "bb_width": 0.2,
        "bb_close_position": "중심선 부근",
        "atr14": None,
        "atr14_ratio_to_close": None,
        "ma5_gap_pct": None,
        "ma10_gap_pct": None,
        "ma20_gap_pct": None,
        "ma60_gap_pct": None,
        "ma120_gap_pct": None,
        "ma240_gap_pct": None,
        "volume_ma5": None,
        "volume_ma20": None,
        "volume_5_20_ratio": None,
        "calculation_version": "v1",
    }


def test_model_and_api_schema_do_not_expose_storage_source() -> None:
    assert not hasattr(StockDailyTechnicalIndicator, "source")
    assert "technical_indicator_source" not in StockDailyPriceResponse.model_fields


def test_upsert_without_source_keeps_one_business_key_row() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE stock_daily_technical_indicators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_id INTEGER NOT NULL,
                trade_date TEXT NOT NULL,
                rsi14 REAL, macd REAL, macd_signal REAL, macd_histogram REAL,
                bb_upper REAL, bb_middle REAL, bb_lower REAL, bb_width REAL, bb_close_position TEXT,
                atr14 REAL, atr14_ratio_to_close REAL,
                ma5_gap_pct REAL, ma10_gap_pct REAL, ma20_gap_pct REAL,
                ma60_gap_pct REAL, ma120_gap_pct REAL, ma240_gap_pct REAL,
                volume_ma5 REAL, volume_ma20 REAL, volume_5_20_ratio REAL,
                calculation_version TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                UNIQUE(stock_id, trade_date)
            )
            """
        )
    session = sessionmaker(bind=engine)()
    try:
        repository = TechnicalIndicatorRepository(session)
        repository.upsert_daily_rows(1, [_indicator_row(rsi14=40.0)])
        repository.upsert_daily_rows(1, [_indicator_row(rsi14=55.0)])
        count, rsi14 = session.execute(
            text("SELECT COUNT(*), MAX(rsi14) FROM stock_daily_technical_indicators")
        ).one()
        assert count == 1
        assert rsi14 == 55.0
    finally:
        session.close()
        engine.dispose()


def test_migration_drops_only_source_and_preserves_rows_and_unique_key() -> None:
    connection = sqlite3.connect(":memory:")
    try:
        connection.executescript(
            """
            CREATE TABLE stock_daily_technical_indicators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_id INTEGER NOT NULL,
                trade_date TEXT NOT NULL,
                rsi14 REAL,
                bb_close_position TEXT,
                source TEXT NOT NULL DEFAULT 'calculated',
                calculation_version TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE UNIQUE INDEX ux_stock_daily_technical_indicators_stock_date
            ON stock_daily_technical_indicators(stock_id, trade_date);
            INSERT INTO stock_daily_technical_indicators
            (stock_id, trade_date, rsi14, bb_close_position, source, calculation_version, created_at, updated_at)
            VALUES (1, '2026-08-25', 55.0, '중심선 부근', 'calculated_from_kiwoom_prices', 'v1', 'now', 'now');
            """
        )
        migration = Path(
            "backend/app/sql/migrations/042_drop_unused_technical_indicator_source.sql"
        ).read_text(encoding="utf-8")
        connection.executescript(migration)

        columns = {row[1] for row in connection.execute("PRAGMA table_info(stock_daily_technical_indicators)")}
        indexes = {
            row[1]: bool(row[2])
            for row in connection.execute("PRAGMA index_list(stock_daily_technical_indicators)")
        }
        row = connection.execute(
            "SELECT stock_id, trade_date, rsi14, bb_close_position, calculation_version "
            "FROM stock_daily_technical_indicators"
        ).fetchone()

        assert "source" not in columns
        assert row == (1, "2026-08-25", 55.0, "중심선 부근", "v1")
        assert indexes["ux_stock_daily_technical_indicators_stock_date"] is True
        assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    finally:
        connection.close()
