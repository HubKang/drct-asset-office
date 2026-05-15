from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.app.core.config import DATABASE_URL, SQLITE_BUSY_TIMEOUT_MS, SQLITE_JOURNAL_MODE, SQLITE_SYNCHRONOUS


class Base(DeclarativeBase):
    pass


if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={
            "check_same_thread": False,
            "timeout": max(1.0, SQLITE_BUSY_TIMEOUT_MS / 1000.0),
        },
    )
else:
    engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # type: ignore[no-untyped-def]
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute(f"PRAGMA journal_mode = {SQLITE_JOURNAL_MODE};")
    cursor.execute(f"PRAGMA synchronous = {SQLITE_SYNCHRONOUS};")
    cursor.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS};")
    cursor.execute("PRAGMA temp_store = MEMORY;")
    cursor.close()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_runtime_schema() -> None:
    if not DATABASE_URL.startswith("sqlite"):
        return

    with engine.begin() as conn:
        rows = conn.exec_driver_sql("PRAGMA table_info(watchlist)").fetchall()
        if not rows:
            return

        columns = {str(row[1]) for row in rows}
        if "is_active" not in columns:
            conn.exec_driver_sql("ALTER TABLE watchlist ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")

        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS stock_daily_market_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_id INTEGER NOT NULL,
                trade_date TEXT NOT NULL,
                market TEXT,
                close_price REAL,
                market_cap INTEGER,
                listed_shares INTEGER,
                trading_volume INTEGER,
                trading_value INTEGER,
                market_cap_rank INTEGER,
                trading_value_rank INTEGER,
                market_trading_value_rank INTEGER,
                trading_value_percentile REAL,
                market_trading_value_percentile REAL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_stock_daily_market_metrics_stock_date_source "
            "ON stock_daily_market_metrics(stock_id, trade_date, source)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_stock_daily_market_metrics_trade_date "
            "ON stock_daily_market_metrics(trade_date)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_stock_daily_market_metrics_stock_id "
            "ON stock_daily_market_metrics(stock_id)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_stock_daily_market_metrics_source "
            "ON stock_daily_market_metrics(source)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_stock_daily_market_metrics_trade_rank "
            "ON stock_daily_market_metrics(trade_date, trading_value_rank)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_stock_daily_market_metrics_trade_market_rank "
            "ON stock_daily_market_metrics(trade_date, market, market_trading_value_rank)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_stock_daily_market_metrics_stock_trade_source "
            "ON stock_daily_market_metrics(stock_id, trade_date, source)"
        )
