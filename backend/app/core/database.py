from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.app.core.config import DATABASE_URL, SQLITE_BUSY_TIMEOUT_MS, SQLITE_JOURNAL_MODE, SQLITE_SYNCHRONOUS
from backend.app.services.gpt_prompt_template_defaults import (
    DEFAULT_GPT_PROMPT_DESCRIPTION,
    DEFAULT_GPT_PROMPT_KEY,
    DEFAULT_GPT_PROMPT_NAME,
    DEFAULT_GPT_PROMPT_TEMPLATE_TEXT,
    DEFAULT_GPT_PROMPT_TYPE,
)
from backend.app.services.market_theme_defaults import DEFAULT_MARKET_THEMES, keywords_json


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
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS gpt_prompt_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt_key TEXT NOT NULL UNIQUE,
                prompt_name TEXT NOT NULL,
                prompt_type TEXT NOT NULL,
                description TEXT,
                template_text TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                is_default INTEGER NOT NULL DEFAULT 0,
                version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            """
            INSERT OR IGNORE INTO gpt_prompt_templates
            (prompt_key, prompt_name, prompt_type, description, template_text, is_active, is_default, version, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                DEFAULT_GPT_PROMPT_KEY,
                DEFAULT_GPT_PROMPT_NAME,
                DEFAULT_GPT_PROMPT_TYPE,
                DEFAULT_GPT_PROMPT_DESCRIPTION,
                DEFAULT_GPT_PROMPT_TEMPLATE_TEXT,
            ),
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_themes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                theme_name TEXT NOT NULL,
                theme_code TEXT NOT NULL UNIQUE,
                theme_type TEXT NOT NULL,
                description TEXT,
                keywords TEXT NOT NULL DEFAULT '[]',
                parent_theme_id INTEGER,
                is_supply_theme INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (parent_theme_id) REFERENCES market_themes(id)
            )
            """
        )
        market_theme_columns = {
            str(row[1]) for row in conn.exec_driver_sql("PRAGMA table_info(market_themes)").fetchall()
        }
        if "is_supply_theme" not in market_theme_columns:
            conn.exec_driver_sql(
                "ALTER TABLE market_themes ADD COLUMN is_supply_theme INTEGER NOT NULL DEFAULT 0"
            )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_theme_stocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                theme_id INTEGER NOT NULL,
                stock_id INTEGER NOT NULL,
                mapping_source TEXT NOT NULL DEFAULT 'manual',
                confidence_score REAL,
                is_primary INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(theme_id, stock_id),
                FOREIGN KEY (theme_id) REFERENCES market_themes(id) ON DELETE CASCADE,
                FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_theme_stock_candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                theme_id INTEGER NOT NULL,
                stock_id INTEGER NOT NULL,
                candidate_source TEXT NOT NULL,
                confidence_score REAL,
                matched_keywords TEXT,
                evidence_count INTEGER NOT NULL DEFAULT 1,
                evidence_summary TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                review_memo TEXT,
                reviewed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(theme_id, stock_id, candidate_source),
                FOREIGN KEY (theme_id) REFERENCES market_themes(id) ON DELETE CASCADE,
                FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_themes_active_sort ON market_themes(is_active, sort_order)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_themes_type ON market_themes(theme_type)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_themes_supply_active_sort "
            "ON market_themes(is_supply_theme, is_active, sort_order)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_theme_stocks_theme_active ON market_theme_stocks(theme_id, is_active)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_theme_stocks_stock_active ON market_theme_stocks(stock_id, is_active)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_theme_stock_candidates_status_updated ON market_theme_stock_candidates(status, updated_at)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_theme_stock_candidates_theme_stock ON market_theme_stock_candidates(theme_id, stock_id)"
        )
        for row in DEFAULT_MARKET_THEMES:
            conn.exec_driver_sql(
                """
                INSERT OR IGNORE INTO market_themes
                (theme_name, theme_code, theme_type, description, keywords, parent_theme_id, is_supply_theme, is_active, sort_order, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, NULL, 0, 1, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (
                    str(row["theme_name"]),
                    str(row["theme_code"]),
                    str(row["theme_type"]),
                    str(row["description"]),
                    keywords_json(list(row["keywords"])),
                    int(row["sort_order"]),
                ),
            )
