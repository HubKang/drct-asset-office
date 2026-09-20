from __future__ import annotations

import sqlite3
from urllib.parse import unquote, urlparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.config import DATABASE_URL, SQLITE_BUSY_TIMEOUT_MS, SQLITE_JOURNAL_MODE, SQLITE_SYNCHRONOUS
from backend.app.services.market_theme_defaults import DEFAULT_MARKET_THEMES, keywords_json


def seed_default_market_themes_once(conn: sqlite3.Connection, *, seed_if_empty: bool) -> None:
    """Seed a new database once without restoring themes deleted by the user."""
    seed_key = "market_themes_defaults_v1"
    conn.execute(
        "CREATE TABLE IF NOT EXISTS runtime_seed_history "
        "(seed_key TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    if conn.execute("SELECT 1 FROM runtime_seed_history WHERE seed_key = ?", (seed_key,)).fetchone():
        return

    theme_count = int(conn.execute("SELECT COUNT(*) FROM market_themes").fetchone()[0])
    if seed_if_empty and theme_count == 0:
        conn.executemany(
            """
            INSERT OR IGNORE INTO market_themes
            (theme_name, theme_code, theme_type, theme_level, description, keywords,
             parent_theme_id, is_supply_theme, is_active, sort_order, created_at, updated_at)
            VALUES (?, ?, ?, 'THEME', ?, ?, NULL, 0, 1, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            [
                (
                    str(row["theme_name"]), str(row["theme_code"]), str(row["theme_type"]),
                    str(row["description"]), keywords_json(list(row["keywords"])), int(row["sort_order"]),
                )
                for row in DEFAULT_MARKET_THEMES
            ],
        )

    conn.execute(
        "INSERT OR IGNORE INTO runtime_seed_history (seed_key, applied_at) VALUES (?, CURRENT_TIMESTAMP)",
        (seed_key,),
    )


def ensure_markdown_content_column(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA table_info(research_reports);").fetchall()
    column_names = {row[1] for row in rows}
    if "markdown_content" not in column_names:
        conn.execute("ALTER TABLE research_reports ADD COLUMN markdown_content TEXT;")


def ensure_stock_master_columns(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA table_info(stocks);").fetchall()
    column_names = {row[1] for row in rows}
    add_columns: list[tuple[str, str]] = [
        ("isin_code", "TEXT"),
        ("corp_name", "TEXT"),
        ("corp_reg_no", "TEXT"),
        ("last_synced_at", "TEXT"),
        ("source", "TEXT"),
        ("security_type", "TEXT"),
    ]
    for column_name, column_type in add_columns:
        if column_name not in column_names:
            conn.execute(f"ALTER TABLE stocks ADD COLUMN {column_name} {column_type};")


def ensure_stock_daily_prices_table(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS stock_daily_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_id INTEGER NOT NULL,
            trade_date TEXT NOT NULL,
            open_price REAL,
            high_price REAL,
            low_price REAL,
            close_price REAL,
            change_price REAL,
            change_rate REAL,
            volume INTEGER,
            trading_value INTEGER,
            ma5 REAL,
            ma10 REAL,
            ma20 REAL,
            ma60 REAL,
            ma120 REAL,
            ma240 REAL,
            source TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
        );
        CREATE UNIQUE INDEX IF NOT EXISTS ux_stock_daily_prices_stock_date ON stock_daily_prices(stock_id, trade_date);
        CREATE INDEX IF NOT EXISTS idx_stock_daily_prices_stock_id ON stock_daily_prices(stock_id);
        CREATE INDEX IF NOT EXISTS idx_stock_daily_prices_stock_date ON stock_daily_prices(stock_id, trade_date);
        CREATE INDEX IF NOT EXISTS idx_stock_daily_prices_stock_trade_date ON stock_daily_prices(stock_id, trade_date);
        CREATE INDEX IF NOT EXISTS idx_stock_daily_prices_trade_date ON stock_daily_prices(trade_date);
        """
    )


def ensure_stock_daily_market_metrics_table(conn: sqlite3.Connection) -> None:
    conn.executescript(
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
        );
        CREATE UNIQUE INDEX IF NOT EXISTS ux_stock_daily_market_metrics_stock_date_source
            ON stock_daily_market_metrics(stock_id, trade_date, source);
        CREATE INDEX IF NOT EXISTS idx_stock_daily_market_metrics_trade_date
            ON stock_daily_market_metrics(trade_date);
        CREATE INDEX IF NOT EXISTS idx_stock_daily_market_metrics_stock_id
            ON stock_daily_market_metrics(stock_id);
        CREATE INDEX IF NOT EXISTS idx_stock_daily_market_metrics_source
            ON stock_daily_market_metrics(source);
        CREATE INDEX IF NOT EXISTS idx_stock_daily_market_metrics_trade_rank
            ON stock_daily_market_metrics(trade_date, trading_value_rank);
        CREATE INDEX IF NOT EXISTS idx_stock_daily_market_metrics_trade_market_rank
            ON stock_daily_market_metrics(trade_date, market, market_trading_value_rank);
        CREATE INDEX IF NOT EXISTS idx_stock_daily_market_metrics_stock_trade_source
            ON stock_daily_market_metrics(stock_id, trade_date, source);
        """
    )


def ensure_stock_daily_technical_indicators_table(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS stock_daily_technical_indicators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_id INTEGER NOT NULL,
            trade_date TEXT NOT NULL,
            rsi14 REAL,
            macd REAL,
            macd_signal REAL,
            macd_histogram REAL,
            bb_upper REAL,
            bb_middle REAL,
            bb_lower REAL,
            bb_width REAL,
            bb_close_position TEXT,
            atr14 REAL,
            atr14_ratio_to_close REAL,
            ma5_gap_pct REAL,
            ma10_gap_pct REAL,
            ma20_gap_pct REAL,
            ma60_gap_pct REAL,
            ma120_gap_pct REAL,
            ma240_gap_pct REAL,
            volume_ma5 REAL,
            volume_ma20 REAL,
            volume_5_20_ratio REAL,
            calculation_version TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
        );
        CREATE UNIQUE INDEX IF NOT EXISTS ux_stock_daily_technical_indicators_stock_date
            ON stock_daily_technical_indicators(stock_id, trade_date);
        CREATE INDEX IF NOT EXISTS idx_stock_daily_technical_indicators_stock_id
            ON stock_daily_technical_indicators(stock_id);
        CREATE INDEX IF NOT EXISTS idx_stock_daily_technical_indicators_trade_date
            ON stock_daily_technical_indicators(trade_date);
        CREATE INDEX IF NOT EXISTS idx_stock_daily_technical_indicators_stock_trade_date
            ON stock_daily_technical_indicators(stock_id, trade_date);
        CREATE INDEX IF NOT EXISTS idx_stock_daily_technical_indicators_rsi14
            ON stock_daily_technical_indicators(rsi14);
        CREATE INDEX IF NOT EXISTS idx_stock_daily_technical_indicators_volume_ratio
            ON stock_daily_technical_indicators(volume_5_20_ratio);
        """
    )


def main() -> None:
    project_root = PROJECT_ROOT
    if not DATABASE_URL.startswith("sqlite:///"):
        raise ValueError(f"init_db.py supports sqlite only. DATABASE_URL={DATABASE_URL}")

    parsed = urlparse(DATABASE_URL)
    raw_path = unquote(parsed.path or "")
    if raw_path.startswith("/./"):
        raw_path = raw_path[1:]
    if raw_path.startswith("/") and len(raw_path) >= 3 and raw_path[2] == ":":
        raw_path = raw_path[1:]

    db_path = Path(raw_path)
    if not db_path.is_absolute():
        db_path = (project_root / db_path).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    schema_path = project_root / "backend" / "app" / "sql" / "schema.sql"

    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    schema_sql = schema_path.read_text(encoding="utf-8")

    with sqlite3.connect(db_path, timeout=max(1.0, SQLITE_BUSY_TIMEOUT_MS / 1000.0)) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute(f"PRAGMA journal_mode = {SQLITE_JOURNAL_MODE};")
        conn.execute(f"PRAGMA synchronous = {SQLITE_SYNCHRONOUS};")
        conn.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS};")
        market_themes_preexisting = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='market_themes'"
        ).fetchone() is not None
        conn.executescript(schema_sql)
        seed_default_market_themes_once(conn, seed_if_empty=not market_themes_preexisting)
        ensure_markdown_content_column(conn)
        ensure_stock_master_columns(conn)
        ensure_stock_daily_prices_table(conn)
        ensure_stock_daily_market_metrics_table(conn)
        ensure_stock_daily_technical_indicators_table(conn)
        conn.commit()

    print(f"[DB] DATABASE_URL={DATABASE_URL}")
    print(f"[DB] sqlite_path={db_path}")
    print(f"[DB] sqlite_journal_mode={SQLITE_JOURNAL_MODE}")
    print(f"[DB] sqlite_synchronous={SQLITE_SYNCHRONOUS}")
    print(f"[DB] sqlite_busy_timeout_ms={SQLITE_BUSY_TIMEOUT_MS}")
    print(f"Database initialized at: {db_path}")


if __name__ == "__main__":
    main()
