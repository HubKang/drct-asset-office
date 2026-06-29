from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.app.core.config import DATABASE_URL, SQLITE_BUSY_TIMEOUT_MS, SQLITE_JOURNAL_MODE, SQLITE_SYNCHRONOUS
from backend.app.services.analysis_indicator_defaults import (
    BASE_OPERATORS,
    DEFAULT_ANALYSIS_ALIASES,
    DEFAULT_ANALYSIS_CONDITION_TEMPLATES,
    DEFAULT_ANALYSIS_INDICATORS,
    json_text,
)
from backend.app.services.gpt_prompt_template_defaults import DEFAULT_GPT_PROMPTS
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
            CREATE TABLE IF NOT EXISTS market_indexes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                index_code TEXT NOT NULL UNIQUE,
                index_name TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT '국내지수',
                market TEXT NOT NULL DEFAULT 'KR',
                currency TEXT NOT NULL DEFAULT 'KRW',
                provider TEXT NOT NULL DEFAULT 'KIWOOM_REST',
                provider_symbol TEXT,
                description TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                display_order INTEGER NOT NULL DEFAULT 0,
                last_collected_date TEXT,
                collection_status TEXT NOT NULL DEFAULT 'NOT_COLLECTED',
                error_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_index_daily_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                index_code TEXT NOT NULL,
                price_date TEXT NOT NULL,
                open_price REAL,
                high_price REAL,
                low_price REAL,
                close_price REAL,
                volume INTEGER,
                trading_value INTEGER,
                change_rate REAL,
                ma5 REAL,
                ma20 REAL,
                ma60 REAL,
                ma120 REAL,
                source_provider TEXT NOT NULL DEFAULT 'KIWOOM_REST',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(index_code, price_date),
                FOREIGN KEY (index_code) REFERENCES market_indexes(index_code) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_index_daily_prices_code_date "
            "ON market_index_daily_prices(index_code, price_date)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_indexes_active_order "
            "ON market_indexes(is_active, display_order)"
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_index_theme_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                index_code TEXT NOT NULL,
                theme_id INTEGER,
                theme_group_id INTEGER,
                mapping_type TEXT NOT NULL DEFAULT 'reference',
                description TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (index_code) REFERENCES market_indexes(index_code) ON DELETE CASCADE,
                FOREIGN KEY (theme_id) REFERENCES market_themes(id) ON DELETE SET NULL
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_index_theme_mappings_index "
            "ON market_index_theme_mappings(index_code, is_active)"
        )

        for row in (
            ("KOSPI", "코스피", "국내대표지수", "KOSPI", "KRW", "KIWOOM_REST", "KOSPI", "한국거래소 유가증권시장 대표 지수", 1, 1),
            ("KOSDAQ", "코스닥", "국내대표지수", "KOSDAQ", "KRW", "KIWOOM_REST", "KOSDAQ", "한국거래소 코스닥시장 대표 지수", 1, 2),
            ("KOSPI200", "코스피200", "국내보조지수", "KOSPI", "KRW", "KIWOOM_REST", None, "코스피200 보조지수. 키움 provider mapping 확인 필요", 1, 3),
            ("KOSDAQ150", "코스닥150", "국내보조지수", "KOSDAQ", "KRW", "KIWOOM_REST", None, "코스닥150 보조지수. 키움 provider mapping 확인 필요", 1, 4),
            ("KOSPI_ELECTRONICS", "코스피 전기전자", "업종지수", "KOSPI", "KRW", "KIWOOM_REST", None, "코스피 전기전자 업종지수. 키움 provider mapping 확인 필요", 1, 10),
            ("KOSPI_PHARMA", "코스피 의약품", "업종지수", "KOSPI", "KRW", "KIWOOM_REST", None, "코스피 의약품 업종지수. 키움 provider mapping 확인 필요", 1, 11),
            ("KOSPI_CHEMICAL", "코스피 화학", "업종지수", "KOSPI", "KRW", "KIWOOM_REST", None, "코스피 화학 업종지수. 키움 provider mapping 확인 필요", 1, 12),
            ("KOSPI_MACHINERY", "코스피 기계", "업종지수", "KOSPI", "KRW", "KIWOOM_REST", None, "코스피 기계 업종지수. 키움 provider mapping 확인 필요", 1, 13),
            ("KOSPI_TRANSPORT_EQUIPMENT", "코스피 운수장비", "업종지수", "KOSPI", "KRW", "KIWOOM_REST", None, "코스피 운수장비 업종지수. 키움 provider mapping 확인 필요", 1, 14),
            ("KOSPI_STEEL_METAL", "코스피 철강금속", "업종지수", "KOSPI", "KRW", "KIWOOM_REST", None, "코스피 철강금속 업종지수. 키움 provider mapping 확인 필요", 1, 15),
            ("KOSPI_FINANCE", "코스피 금융업", "업종지수", "KOSPI", "KRW", "KIWOOM_REST", None, "코스피 금융업 업종지수. 키움 provider mapping 확인 필요", 1, 16),
            ("KOSPI_CONSTRUCTION", "코스피 건설업", "업종지수", "KOSPI", "KRW", "KIWOOM_REST", None, "코스피 건설업 업종지수. 키움 provider mapping 확인 필요", 1, 17),
            ("KOSPI_TRANSPORT_WAREHOUSE", "코스피 운수창고", "업종지수", "KOSPI", "KRW", "KIWOOM_REST", None, "코스피 운수창고 업종지수. 키움 provider mapping 확인 필요", 1, 18),
            ("KOSPI_SERVICE", "코스피 서비스업", "업종지수", "KOSPI", "KRW", "KIWOOM_REST", None, "코스피 서비스업 업종지수. 키움 provider mapping 확인 필요", 1, 19),
            ("KOSDAQ_SEMICONDUCTOR", "코스닥 반도체", "업종지수", "KOSDAQ", "KRW", "KIWOOM_REST", None, "코스닥 반도체 업종지수. 키움 provider mapping 확인 필요", 1, 30),
            ("KOSDAQ_IT_HW", "코스닥 IT H/W", "업종지수", "KOSDAQ", "KRW", "KIWOOM_REST", None, "코스닥 IT H/W 업종지수. 키움 provider mapping 확인 필요", 1, 31),
            ("KOSDAQ_IT_SW_SVC", "코스닥 IT S/W & SVC", "업종지수", "KOSDAQ", "KRW", "KIWOOM_REST", None, "코스닥 IT S/W & SVC 업종지수. 키움 provider mapping 확인 필요", 1, 32),
            ("KOSDAQ_PHARMA", "코스닥 제약", "업종지수", "KOSDAQ", "KRW", "KIWOOM_REST", None, "코스닥 제약 업종지수. 키움 provider mapping 확인 필요", 1, 33),
            ("KOSDAQ_GENERAL_ELECTRONICS", "코스닥 일반전기전자", "업종지수", "KOSDAQ", "KRW", "KIWOOM_REST", None, "코스닥 일반전기전자 업종지수. 키움 provider mapping 확인 필요", 1, 34),
            ("KOSDAQ_MACHINE_EQUIPMENT", "코스닥 기계·장비", "업종지수", "KOSDAQ", "KRW", "KIWOOM_REST", None, "코스닥 기계·장비 업종지수. 키움 provider mapping 확인 필요", 1, 35),
            ("KOSDAQ_CHEMICAL", "코스닥 화학", "업종지수", "KOSDAQ", "KRW", "KIWOOM_REST", None, "코스닥 화학 업종지수. 키움 provider mapping 확인 필요", 1, 36),
            ("KOSDAQ_MEDICAL_PRECISION", "코스닥 의료·정밀기기", "업종지수", "KOSDAQ", "KRW", "KIWOOM_REST", None, "코스닥 의료·정밀기기 업종지수. 키움 provider mapping 확인 필요", 1, 37),
            ("GOLD_KRX", "KRX 금 현물", "금현물", "KRX", "KRW", "KIWOOM_REST", None, "KRX 금 현물. 키움 provider mapping 확인 필요", 1, 50),
        ):
            conn.exec_driver_sql(
                """
                INSERT OR IGNORE INTO market_indexes
                (index_code, index_name, category, market, currency, provider, provider_symbol, description, is_active, display_order, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                row,
            )
            conn.exec_driver_sql(
                """
                UPDATE market_indexes
                SET index_name = CASE WHEN index_name IS NULL OR TRIM(index_name) = '' OR index_name LIKE '%?%' THEN ? ELSE index_name END,
                    category = ?,
                    market = ?,
                    currency = ?,
                    provider = ?,
                    provider_symbol = ?,
                    description = CASE WHEN description IS NULL OR TRIM(description) = '' OR description LIKE '%?%' THEN ? ELSE description END,
                    is_active = ?,
                    display_order = ?,
                    collection_status = CASE
                        WHEN collection_status IN ('ready', 'READY', '', 'success', 'SUCCESS') OR collection_status IS NULL THEN
                            CASE WHEN last_collected_date IS NULL THEN 'NOT_COLLECTED' ELSE 'LATEST' END
                        WHEN collection_status IN ('failed', 'FAILED') THEN 'ERROR'
                        ELSE collection_status
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE index_code = ?
                """,
                (row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9], row[0]),
            )

        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS gpt_prompt_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT NOT NULL DEFAULT 'common',
                prompt_key TEXT NOT NULL UNIQUE,
                prompt_name TEXT NOT NULL,
                description TEXT,
                prompt_text TEXT NOT NULL,
                default_prompt_text TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        gpt_prompt_columns = {
            str(row[1]) for row in conn.exec_driver_sql("PRAGMA table_info(gpt_prompt_templates)").fetchall()
        }
        if "domain" not in gpt_prompt_columns:
            conn.exec_driver_sql("ALTER TABLE gpt_prompt_templates ADD COLUMN domain TEXT NOT NULL DEFAULT 'common'")
        if "prompt_text" not in gpt_prompt_columns:
            conn.exec_driver_sql("ALTER TABLE gpt_prompt_templates ADD COLUMN prompt_text TEXT")
            conn.exec_driver_sql("UPDATE gpt_prompt_templates SET prompt_text = COALESCE(template_text, '')")
        if "default_prompt_text" not in gpt_prompt_columns:
            conn.exec_driver_sql("ALTER TABLE gpt_prompt_templates ADD COLUMN default_prompt_text TEXT")
            conn.exec_driver_sql("UPDATE gpt_prompt_templates SET default_prompt_text = COALESCE(prompt_text, '')")
        if "sort_order" not in gpt_prompt_columns:
            conn.exec_driver_sql("ALTER TABLE gpt_prompt_templates ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0")

        for row in DEFAULT_GPT_PROMPTS:
            conn.exec_driver_sql(
                """
                INSERT OR IGNORE INTO gpt_prompt_templates
                (domain, prompt_key, prompt_name, prompt_type, description, prompt_text, default_prompt_text, is_active, sort_order, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (
                    str(row["domain"]),
                    str(row["prompt_key"]),
                    str(row["prompt_name"]),
                    str(row["domain"]),
                    str(row["description"]),
                    str(row["default_prompt_text"]),
                    str(row["default_prompt_text"]),
                    int(row["sort_order"]),
                ),
            )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_themes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                theme_name TEXT NOT NULL,
                theme_code TEXT NOT NULL UNIQUE,
                theme_type TEXT NOT NULL,
                theme_level TEXT NOT NULL DEFAULT 'THEME',
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
        if "theme_level" not in market_theme_columns:
            conn.exec_driver_sql(
                "ALTER TABLE market_themes ADD COLUMN theme_level TEXT NOT NULL DEFAULT 'THEME'"
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
            """
            CREATE TABLE IF NOT EXISTS market_theme_daily_returns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                theme_id INTEGER NOT NULL,
                return_date TEXT NOT NULL,
                avg_change_rate REAL,
                stock_count INTEGER NOT NULL DEFAULT 0,
                success_stock_count INTEGER NOT NULL DEFAULT 0,
                failed_stock_count INTEGER NOT NULL DEFAULT 0,
                rising_stock_count INTEGER NOT NULL DEFAULT 0,
                falling_stock_count INTEGER NOT NULL DEFAULT 0,
                flat_stock_count INTEGER NOT NULL DEFAULT 0,
                total_trading_value INTEGER NOT NULL DEFAULT 0,
                total_trading_value_100m REAL,
                data_source TEXT NOT NULL DEFAULT 'kiwoom',
                first_created_at TEXT NOT NULL,
                last_refreshed_at TEXT NOT NULL,
                refresh_count INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(theme_id, return_date),
                FOREIGN KEY (theme_id) REFERENCES market_themes(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_theme_stock_daily_returns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                theme_daily_return_id INTEGER NOT NULL,
                theme_id INTEGER NOT NULL,
                stock_id INTEGER NOT NULL,
                stock_code TEXT,
                stock_name TEXT,
                return_date TEXT NOT NULL,
                change_rate REAL,
                trading_value INTEGER,
                trading_value_100m REAL,
                current_price INTEGER,
                data_status TEXT NOT NULL DEFAULT 'missing',
                error_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(theme_id, stock_id, return_date),
                FOREIGN KEY (theme_daily_return_id) REFERENCES market_theme_daily_returns(id) ON DELETE CASCADE,
                FOREIGN KEY (theme_id) REFERENCES market_themes(id) ON DELETE CASCADE,
                FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_theme_daily_returns_date ON market_theme_daily_returns(return_date)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_theme_daily_returns_theme_date ON market_theme_daily_returns(theme_id, return_date)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_theme_stock_daily_returns_theme_date ON market_theme_stock_daily_returns(theme_id, return_date)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_themes_active_sort ON market_themes(is_active, sort_order)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_themes_type ON market_themes(theme_type)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_themes_level_parent ON market_themes(theme_level, parent_theme_id)"
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_calendar_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                theme_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                summary TEXT,
                news_url TEXT,
                event_type TEXT NOT NULL DEFAULT 'news',
                importance TEXT NOT NULL DEFAULT 'medium',
                memo TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (theme_id) REFERENCES market_themes(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_calendar_event_stocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                stock_id INTEGER NOT NULL,
                stock_code TEXT,
                stock_name TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(event_id, stock_id),
                FOREIGN KEY (event_id) REFERENCES market_calendar_events(id) ON DELETE CASCADE,
                FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_calendar_events_range ON market_calendar_events(start_date, end_date)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_calendar_events_theme ON market_calendar_events(theme_id, is_active)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_calendar_event_stocks_event ON market_calendar_event_stocks(event_id)"
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS stock_tracking_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                success_rule_note TEXT,
                fail_rule_note TEXT,
                observation_note TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_stock_tracking_groups_active ON stock_tracking_groups(is_active, updated_at)"
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS stock_tracking_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                candidate_id INTEGER,
                condition_no TEXT,
                condition_name TEXT,
                stock_id INTEGER,
                stock_code TEXT,
                stock_name TEXT,
                detected_date TEXT,
                tracking_base_date TEXT NOT NULL,
                base_price REAL,
                base_change_rate REAL,
                base_volume INTEGER,
                base_trading_value INTEGER,
                status TEXT NOT NULL DEFAULT 'TRACKING',
                review_date TEXT,
                review_note TEXT,
                price_status TEXT NOT NULL DEFAULT 'NOT_COLLECTED',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (group_id) REFERENCES stock_tracking_groups(id) ON DELETE CASCADE,
                FOREIGN KEY (candidate_id) REFERENCES market_trend_events(id) ON DELETE SET NULL,
                FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE SET NULL
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_stock_tracking_items_group_candidate ON stock_tracking_items(group_id, candidate_id) WHERE candidate_id IS NOT NULL"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_stock_tracking_items_group ON stock_tracking_items(group_id)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_stock_tracking_items_status ON stock_tracking_items(status, price_status)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_stock_tracking_items_base_date ON stock_tracking_items(tracking_base_date)"
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS stock_tracking_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tracking_item_id INTEGER NOT NULL,
                image_path TEXT NOT NULL,
                original_filename TEXT,
                image_type TEXT NOT NULL,
                caption TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (tracking_item_id) REFERENCES stock_tracking_items(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_stock_tracking_images_item ON stock_tracking_images(tracking_item_id, id)"
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS price_collection_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL,
                source_id INTEGER NOT NULL,
                stock_id INTEGER,
                stock_code TEXT,
                base_date TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT,
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                last_collected_date TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(source_type, source_id)
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_price_collection_targets_source ON price_collection_targets(source_type, source_id)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_price_collection_targets_status ON price_collection_targets(status, source_type)"
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
                (theme_name, theme_code, theme_type, theme_level, description, keywords, parent_theme_id, is_supply_theme, is_active, sort_order, created_at, updated_at)
                VALUES (?, ?, ?, 'THEME', ?, ?, NULL, 0, 1, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
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

        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS trend_detection_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                setting_key TEXT NOT NULL UNIQUE,
                setting_name TEXT NOT NULL,
                min_market_cap INTEGER NOT NULL,
                min_trading_value INTEGER NOT NULL,
                min_change_rate REAL NOT NULL,
                min_intraday_range_rate REAL,
                use_market_cap INTEGER NOT NULL DEFAULT 1,
                use_trading_value INTEGER NOT NULL DEFAULT 1,
                use_change_rate INTEGER NOT NULL DEFAULT 1,
                use_intraday_range INTEGER NOT NULL DEFAULT 0,
                market_scope TEXT NOT NULL DEFAULT 'ALL',
                is_active INTEGER NOT NULL DEFAULT 1,
                is_default INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        trend_setting_columns = {
            str(row[1]) for row in conn.exec_driver_sql("PRAGMA table_info(trend_detection_settings)").fetchall()
        }
        if "use_market_cap" not in trend_setting_columns:
            conn.exec_driver_sql("ALTER TABLE trend_detection_settings ADD COLUMN use_market_cap INTEGER NOT NULL DEFAULT 1")
        if "use_trading_value" not in trend_setting_columns:
            conn.exec_driver_sql("ALTER TABLE trend_detection_settings ADD COLUMN use_trading_value INTEGER NOT NULL DEFAULT 1")
        if "use_change_rate" not in trend_setting_columns:
            conn.exec_driver_sql("ALTER TABLE trend_detection_settings ADD COLUMN use_change_rate INTEGER NOT NULL DEFAULT 1")
        conn.exec_driver_sql(
            """
            INSERT OR IGNORE INTO trend_detection_settings
            (setting_key, setting_name, min_market_cap, min_trading_value, min_change_rate, min_intraday_range_rate,
             use_market_cap, use_trading_value, use_change_rate, use_intraday_range, market_scope, is_active, is_default, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                "default_supply_event",
                "기본 수급 이벤트 감지 조건",
                200_000_000_000,
                50_000_000_000,
                15.0,
                6.0,
                1,
                1,
                1,
                0,
                "ALL",
                1,
                1,
            ),
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_trend_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_date TEXT NOT NULL,
                stock_id INTEGER NOT NULL,
                stock_code TEXT,
                stock_name TEXT,
                market_type TEXT,
                market_cap INTEGER,
                trading_value INTEGER,
                change_rate REAL,
                intraday_range_rate REAL,
                event_type TEXT NOT NULL DEFAULT 'supply_surge',
                detection_setting_id INTEGER,
                applied_min_market_cap INTEGER,
                applied_min_trading_value INTEGER,
                applied_min_change_rate REAL,
                applied_min_intraday_range_rate REAL,
                applied_use_market_cap INTEGER,
                applied_use_trading_value INTEGER,
                applied_use_change_rate INTEGER,
                applied_use_intraday_range INTEGER,
                theme_id INTEGER,
                theme_status TEXT NOT NULL DEFAULT 'unassigned',
                primary_theme_id INTEGER,
                reason_summary TEXT,
                user_memo TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(trade_date, stock_id, event_type),
                FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE,
                FOREIGN KEY (theme_id) REFERENCES market_themes(id),
                FOREIGN KEY (primary_theme_id) REFERENCES market_themes(id),
                FOREIGN KEY (detection_setting_id) REFERENCES trend_detection_settings(id)
            )
            """
        )
        market_trend_event_columns = {
            str(row[1]) for row in conn.exec_driver_sql("PRAGMA table_info(market_trend_events)").fetchall()
        }
        if "detection_source" not in market_trend_event_columns:
            conn.exec_driver_sql(
                "ALTER TABLE market_trend_events ADD COLUMN detection_source TEXT"
            )
        if "applied_use_market_cap" not in market_trend_event_columns:
            conn.exec_driver_sql("ALTER TABLE market_trend_events ADD COLUMN applied_use_market_cap INTEGER")
        if "applied_use_trading_value" not in market_trend_event_columns:
            conn.exec_driver_sql("ALTER TABLE market_trend_events ADD COLUMN applied_use_trading_value INTEGER")
        if "applied_use_change_rate" not in market_trend_event_columns:
            conn.exec_driver_sql("ALTER TABLE market_trend_events ADD COLUMN applied_use_change_rate INTEGER")
        if "condition_seq" not in market_trend_event_columns:
            conn.exec_driver_sql("ALTER TABLE market_trend_events ADD COLUMN condition_seq TEXT")
        if "condition_name" not in market_trend_event_columns:
            conn.exec_driver_sql("ALTER TABLE market_trend_events ADD COLUMN condition_name TEXT")
        if "detected_at" not in market_trend_event_columns:
            conn.exec_driver_sql("ALTER TABLE market_trend_events ADD COLUMN detected_at TEXT")
        if "deleted_at" not in market_trend_event_columns:
            conn.exec_driver_sql("ALTER TABLE market_trend_events ADD COLUMN deleted_at TEXT")
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_trend_event_theme_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                market_theme_id INTEGER NOT NULL,
                link_reason TEXT,
                user_memo TEXT,
                is_primary INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                deleted_at TEXT,
                UNIQUE(event_id, market_theme_id),
                FOREIGN KEY (event_id) REFERENCES market_trend_events(id) ON DELETE CASCADE,
                FOREIGN KEY (market_theme_id) REFERENCES market_themes(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_price_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_date TEXT NOT NULL,
                snapshot_time TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'pykrx',
                market_scope TEXT NOT NULL DEFAULT 'ALL',
                stock_id INTEGER,
                stock_code TEXT NOT NULL,
                stock_name TEXT,
                market_type TEXT,
                open_price INTEGER,
                high_price INTEGER,
                low_price INTEGER,
                close_price INTEGER,
                volume INTEGER,
                trading_value INTEGER,
                market_cap INTEGER,
                change_rate REAL,
                intraday_range_rate REAL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE SET NULL
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS kiwoom_condition_searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                condition_seq TEXT NOT NULL,
                condition_name TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'kiwoom_rest',
                is_active INTEGER NOT NULL DEFAULT 1,
                last_synced_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(source, condition_seq)
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS kiwoom_condition_result_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                condition_id INTEGER,
                condition_seq TEXT NOT NULL,
                condition_name TEXT,
                stock_code TEXT NOT NULL,
                stock_code_raw TEXT,
                stock_name TEXT,
                current_price INTEGER,
                change_rate REAL,
                intraday_change_rate REAL,
                trading_value INTEGER,
                volume INTEGER,
                detected_at TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'kiwoom_rest',
                source_api TEXT,
                raw_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (condition_id) REFERENCES kiwoom_condition_searches(id) ON DELETE SET NULL
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS daily_theme_flow_ranks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_date TEXT NOT NULL,
                market_theme_id INTEGER NOT NULL,
                auto_rank INTEGER,
                manual_rank INTEGER,
                final_rank INTEGER,
                rank_score REAL NOT NULL DEFAULT 0,
                rank_basis TEXT NOT NULL DEFAULT 'auto',
                user_memo TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(trade_date, market_theme_id),
                FOREIGN KEY (market_theme_id) REFERENCES market_themes(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_trend_detection_settings_active_default "
            "ON trend_detection_settings(is_active, is_default, updated_at)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_trend_events_trade_date_active "
            "ON market_trend_events(trade_date, is_active)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_trend_events_theme_status "
            "ON market_trend_events(theme_status, trade_date, is_active)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_trend_events_detection_source "
            "ON market_trend_events(detection_source, trade_date, is_active)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_trend_events_condition_seq "
            "ON market_trend_events(condition_seq, trade_date, is_active)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_trend_event_theme_links_event_active "
            "ON market_trend_event_theme_links(event_id, is_active)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_trend_event_theme_links_theme_active "
            "ON market_trend_event_theme_links(market_theme_id, is_active)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_price_snapshots_stock_code "
            "ON market_price_snapshots(stock_code)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_price_snapshots_snapshot_date "
            "ON market_price_snapshots(snapshot_date)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_price_snapshots_market_type "
            "ON market_price_snapshots(market_type)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_price_snapshots_trading_value "
            "ON market_price_snapshots(trading_value)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_price_snapshots_change_rate "
            "ON market_price_snapshots(change_rate)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_price_snapshots_market_cap "
            "ON market_price_snapshots(market_cap)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_kiwoom_condition_searches_source_seq "
            "ON kiwoom_condition_searches(source, condition_seq)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_kiwoom_condition_result_items_condition_seq "
            "ON kiwoom_condition_result_items(condition_seq)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_kiwoom_condition_result_items_stock_code "
            "ON kiwoom_condition_result_items(stock_code)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_kiwoom_condition_result_items_detected_at "
            "ON kiwoom_condition_result_items(detected_at)"
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS briefing_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL,
                source_name TEXT NOT NULL,
                source_url TEXT NOT NULL,
                channel_id TEXT,
                playlist_id TEXT,
                is_default INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                last_checked_at TEXT,
                deleted_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        briefing_source_columns = {
            str(row[1]) for row in conn.exec_driver_sql("PRAGMA table_info(briefing_sources)").fetchall()
        }
        if "deleted_at" not in briefing_source_columns:
            conn.exec_driver_sql("ALTER TABLE briefing_sources ADD COLUMN deleted_at TEXT")
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS briefing_videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER,
                video_id TEXT NOT NULL UNIQUE,
                video_url TEXT NOT NULL,
                title TEXT NOT NULL,
                channel_name TEXT,
                published_at TEXT,
                duration_seconds INTEGER,
                thumbnail_url TEXT,
                description_summary TEXT,
                transcript_status TEXT NOT NULL DEFAULT 'unknown',
                transcript_language TEXT,
                transcript_source TEXT,
                transcript_checked_at TEXT,
                transcript_text_length INTEGER,
                transcript_chunk_count INTEGER,
                llm_response_length INTEGER,
                llm_timeout_seconds INTEGER,
                analysis_status TEXT NOT NULL DEFAULT 'pending',
                last_analyzed_at TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (source_id) REFERENCES briefing_sources(id) ON DELETE SET NULL
            )
            """
        )
        briefing_video_columns = {
            str(row[1]) for row in conn.exec_driver_sql("PRAGMA table_info(briefing_videos)").fetchall()
        }
        if "transcript_checked_at" not in briefing_video_columns:
            conn.exec_driver_sql("ALTER TABLE briefing_videos ADD COLUMN transcript_checked_at TEXT")
        if "transcript_text_length" not in briefing_video_columns:
            conn.exec_driver_sql("ALTER TABLE briefing_videos ADD COLUMN transcript_text_length INTEGER")
        if "transcript_chunk_count" not in briefing_video_columns:
            conn.exec_driver_sql("ALTER TABLE briefing_videos ADD COLUMN transcript_chunk_count INTEGER")
        if "llm_response_length" not in briefing_video_columns:
            conn.exec_driver_sql("ALTER TABLE briefing_videos ADD COLUMN llm_response_length INTEGER")
        if "llm_timeout_seconds" not in briefing_video_columns:
            conn.exec_driver_sql("ALTER TABLE briefing_videos ADD COLUMN llm_timeout_seconds INTEGER")
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS briefing_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER NOT NULL,
                summary_type TEXT NOT NULL,
                model_name TEXT,
                summary_text TEXT,
                key_points_json TEXT,
                topic_json TEXT,
                stock_mentions_json TEXT,
                theme_mentions_json TEXT,
                risk_points_json TEXT,
                quality_meta_json TEXT,
                elapsed_seconds INTEGER,
                chunk_count INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (video_id) REFERENCES briefing_videos(id) ON DELETE CASCADE
            )
            """
        )
        briefing_summary_columns = {
            str(row[1]) for row in conn.exec_driver_sql("PRAGMA table_info(briefing_summaries)").fetchall()
        }
        if "elapsed_seconds" not in briefing_summary_columns:
            conn.exec_driver_sql("ALTER TABLE briefing_summaries ADD COLUMN elapsed_seconds INTEGER")
        if "chunk_count" not in briefing_summary_columns:
            conn.exec_driver_sql("ALTER TABLE briefing_summaries ADD COLUMN chunk_count INTEGER")
        if "quality_meta_json" not in briefing_summary_columns:
            conn.exec_driver_sql("ALTER TABLE briefing_summaries ADD COLUMN quality_meta_json TEXT")
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS briefing_topic_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER NOT NULL,
                topic_name TEXT NOT NULL,
                summary TEXT,
                importance_score INTEGER,
                related_themes_json TEXT,
                related_stocks_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (video_id) REFERENCES briefing_videos(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS briefing_theme_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER NOT NULL,
                market_theme_id INTEGER NOT NULL,
                link_reason TEXT,
                confidence_level TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(video_id, market_theme_id),
                FOREIGN KEY (video_id) REFERENCES briefing_videos(id) ON DELETE CASCADE,
                FOREIGN KEY (market_theme_id) REFERENCES market_themes(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS briefing_summary_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT NOT NULL,
                status TEXT NOT NULL,
                progress_percent INTEGER NOT NULL DEFAULT 0,
                current_step TEXT,
                current_chunk INTEGER NOT NULL DEFAULT 0,
                total_chunks INTEGER NOT NULL DEFAULT 0,
                summary_id INTEGER,
                error_message TEXT,
                started_at TEXT,
                finished_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_briefing_sources_source_type ON briefing_sources(source_type)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_briefing_sources_playlist_id ON briefing_sources(playlist_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_briefing_sources_channel_id ON briefing_sources(channel_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_briefing_sources_is_active ON briefing_sources(is_active)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_briefing_videos_source_id ON briefing_videos(source_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_briefing_videos_video_id ON briefing_videos(video_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_briefing_videos_published_at ON briefing_videos(published_at)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_briefing_videos_analysis_status ON briefing_videos(analysis_status)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_briefing_videos_transcript_status ON briefing_videos(transcript_status)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_briefing_summaries_video_id ON briefing_summaries(video_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_briefing_summaries_summary_type ON briefing_summaries(summary_type)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_briefing_topic_items_video_id ON briefing_topic_items(video_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_briefing_topic_items_topic_name ON briefing_topic_items(topic_name)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_briefing_summary_jobs_video_id ON briefing_summary_jobs(video_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_briefing_summary_jobs_status ON briefing_summary_jobs(status)")
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS telegram_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name TEXT NOT NULL,
                channel_username TEXT NOT NULL,
                channel_title TEXT,
                source_type TEXT NOT NULL DEFAULT 'channel',
                description TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                is_default INTEGER NOT NULL DEFAULT 0,
                is_deleted INTEGER NOT NULL DEFAULT 0,
                last_collected_message_id INTEGER,
                last_collected_at TEXT,
                memo TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS telegram_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL,
                telegram_message_id INTEGER NOT NULL,
                message_date TEXT NOT NULL,
                message_text TEXT,
                message_text_length INTEGER,
                item_title TEXT,
                item_url TEXT,
                normalized_url TEXT,
                publisher TEXT,
                message_type TEXT NOT NULL DEFAULT 'unknown',
                item_category TEXT NOT NULL DEFAULT '기타',
                summary_text TEXT,
                key_points_json TEXT,
                summary_error_message TEXT,
                tag TEXT,
                score INTEGER NOT NULL DEFAULT 50,
                sentiment TEXT NOT NULL DEFAULT 'neutral',
                risk_level TEXT NOT NULL DEFAULT 'unknown',
                event_type TEXT NOT NULL DEFAULT '기타',
                related_stock_code TEXT,
                related_stock_name TEXT,
                related_theme TEXT,
                llm_model TEXT,
                summary_status TEXT NOT NULL DEFAULT 'pending',
                summary_has_content INTEGER NOT NULL DEFAULT 0,
                analysis_status TEXT NOT NULL DEFAULT 'pending',
                collected_at TEXT NOT NULL,
                summarized_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                FOREIGN KEY (source_id) REFERENCES telegram_sources(id)
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS telegram_daily_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                summary_date TEXT NOT NULL,
                source_id INTEGER NOT NULL DEFAULT 0,
                item_count INTEGER NOT NULL DEFAULT 0,
                summary_text TEXT,
                key_points_json TEXT,
                theme_mentions_json TEXT,
                stock_mentions_json TEXT,
                risk_points_json TEXT,
                top_tags_json TEXT,
                top_event_types_json TEXT,
                message_type_stats_json TEXT,
                market_view TEXT,
                summary_has_content INTEGER NOT NULL DEFAULT 0,
                llm_model TEXT,
                elapsed_seconds INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                FOREIGN KEY (source_id) REFERENCES telegram_sources(id)
            )
            """
        )
        conn.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ux_telegram_sources_channel_username ON telegram_sources(channel_username)")
        conn.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ux_telegram_items_source_msg ON telegram_items(source_id, telegram_message_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_telegram_items_message_date ON telegram_items(message_date)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_telegram_items_source_date ON telegram_items(source_id, message_date)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_telegram_items_message_type ON telegram_items(message_type)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_telegram_items_tag ON telegram_items(tag)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_telegram_items_normalized_url ON telegram_items(normalized_url)")
        telegram_item_columns = {
            str(row[1]) for row in conn.exec_driver_sql("PRAGMA table_info(telegram_items)").fetchall()
        }
        if "summary_error_message" not in telegram_item_columns:
            conn.exec_driver_sql("ALTER TABLE telegram_items ADD COLUMN summary_error_message TEXT")
        conn.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ux_telegram_daily_summaries_date_source ON telegram_daily_summaries(summary_date, source_id)")
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS trade_methods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                method_name TEXT NOT NULL,
                core_concept TEXT,
                description TEXT,
                buy_condition TEXT,
                sell_condition TEXT,
                position_sizing_rule TEXT,
                entry_rule TEXT,
                exit_rule TEXT,
                stop_loss_rule TEXT,
                take_profit_rule TEXT,
                checklist TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT
            )
            """
        )
        trade_method_columns = {
            str(row[1]) for row in conn.exec_driver_sql("PRAGMA table_info(trade_methods)").fetchall()
        }
        for column_name in ("core_concept", "buy_condition", "sell_condition", "position_sizing_rule", "checklist"):
            if column_name not in trade_method_columns:
                conn.exec_driver_sql(f"ALTER TABLE trade_methods ADD COLUMN {column_name} TEXT")
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS trade_journals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                buy_date TEXT NOT NULL,
                sell_date TEXT,
                stock_code TEXT,
                stock_name TEXT NOT NULL,
                stock_theme TEXT,
                trade_method_id INTEGER,
                trade_method_name TEXT,
                result_type TEXT,
                profit_rate REAL,
                realized_profit INTEGER,
                buy_price REAL,
                buy_quantity INTEGER,
                buy_amount INTEGER,
                sell_price REAL,
                sell_quantity INTEGER,
                sell_amount INTEGER,
                trade_reason TEXT,
                success_reason TEXT,
                failure_reason TEXT,
                review_memo TEXT,
                remark TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                FOREIGN KEY (trade_method_id) REFERENCES trade_methods(id)
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS trade_journal_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_journal_id INTEGER NOT NULL,
                image_type TEXT NOT NULL,
                image_path TEXT NOT NULL,
                image_memo TEXT,
                original_filename TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (trade_journal_id) REFERENCES trade_journals(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS trade_method_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_method_id INTEGER NOT NULL,
                image_type TEXT NOT NULL DEFAULT 'example_chart',
                image_path TEXT NOT NULL,
                image_memo TEXT,
                original_filename TEXT,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                FOREIGN KEY (trade_method_id) REFERENCES trade_methods(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_trade_method_images_method_id ON trade_method_images(trade_method_id)"
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS trade_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_id INTEGER NOT NULL DEFAULT 0,
                decision_id INTEGER,
                review_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                result_summary TEXT,
                what_was_right TEXT,
                what_was_wrong TEXT,
                lesson_learned TEXT,
                journal_id INTEGER NOT NULL,
                method_id INTEGER,
                review_status TEXT DEFAULT '미복기',
                trade_grade TEXT,
                principle_followed TEXT,
                entry_quality TEXT,
                exit_quality TEXT,
                risk_control_quality TEXT,
                emotion_control_quality TEXT,
                impulse_trade INTEGER DEFAULT 0,
                main_mistake TEXT,
                good_point TEXT,
                improvement_point TEXT,
                next_action TEXT,
                review_memo TEXT,
                gpt_review_text TEXT,
                reviewed_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (journal_id) REFERENCES trade_journals(id),
                FOREIGN KEY (method_id) REFERENCES trade_methods(id)
            )
            """
        )
        trade_review_columns = {
            str(row[1]) for row in conn.exec_driver_sql("PRAGMA table_info(trade_reviews)").fetchall()
        }
        trade_review_column_defs = {
            "journal_id": "INTEGER",
            "method_id": "INTEGER",
            "review_status": "TEXT DEFAULT '미복기'",
            "trade_grade": "TEXT",
            "principle_followed": "TEXT",
            "entry_quality": "TEXT",
            "exit_quality": "TEXT",
            "risk_control_quality": "TEXT",
            "emotion_control_quality": "TEXT",
            "impulse_trade": "INTEGER DEFAULT 0",
            "main_mistake": "TEXT",
            "good_point": "TEXT",
            "improvement_point": "TEXT",
            "next_action": "TEXT",
            "review_memo": "TEXT",
            "gpt_review_text": "TEXT",
            "reviewed_at": "TEXT",
            "updated_at": "TEXT",
        }
        for column_name, column_def in trade_review_column_defs.items():
            if column_name not in trade_review_columns:
                conn.exec_driver_sql(f"ALTER TABLE trade_reviews ADD COLUMN {column_name} {column_def}")
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS trade_review_check_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                review_id INTEGER NOT NULL,
                journal_id INTEGER NOT NULL,
                method_id INTEGER,
                item_type TEXT NOT NULL,
                item_order INTEGER DEFAULT 0,
                item_text TEXT NOT NULL,
                is_checked INTEGER DEFAULT 0,
                note TEXT,
                source_field TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (review_id) REFERENCES trade_reviews(id)
            )
            """
        )
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_trade_methods_active_sort ON trade_methods(is_active, sort_order)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_trade_journals_buy_date ON trade_journals(buy_date)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_trade_journals_method_id ON trade_journals(trade_method_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_trade_journals_result_type ON trade_journals(result_type)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_trade_journal_images_journal_id ON trade_journal_images(trade_journal_id)")
        conn.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ux_trade_reviews_journal_id ON trade_reviews(journal_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_trade_reviews_status ON trade_reviews(review_status)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_trade_reviews_grade ON trade_reviews(trade_grade)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_trade_review_check_items_review_id ON trade_review_check_items(review_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_trade_review_check_items_journal_id ON trade_review_check_items(journal_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_trade_review_check_items_type ON trade_review_check_items(item_type)")
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS simulation_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code TEXT NOT NULL,
                stock_name TEXT,
                method_id INTEGER,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                current_date TEXT,
                current_index INTEGER DEFAULT 0,
                initial_cash REAL NOT NULL,
                cash REAL NOT NULL,
                position_qty INTEGER DEFAULT 0,
                avg_price REAL DEFAULT 0,
                realized_profit REAL DEFAULT 0,
                status TEXT DEFAULT '진행중',
                options_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        simulation_session_columns = {
            str(row[1]) for row in conn.exec_driver_sql("PRAGMA table_info(simulation_sessions)").fetchall()
        }
        if "method_id" not in simulation_session_columns:
            conn.exec_driver_sql("ALTER TABLE simulation_sessions ADD COLUMN method_id INTEGER")
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_simulation_sessions_stock_code ON simulation_sessions(stock_code)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_simulation_sessions_method_id ON simulation_sessions(method_id)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_simulation_sessions_status ON simulation_sessions(status)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_simulation_sessions_created_at ON simulation_sessions(created_at)"
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS simulation_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                trade_date TEXT NOT NULL,
                side TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                fee REAL DEFAULT 0,
                amount REAL NOT NULL,
                realized_profit REAL DEFAULT 0,
                reason TEXT,
                method_review_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES simulation_sessions(id)
            )
            """
        )
        simulation_trade_columns = {
            str(row[1]) for row in conn.exec_driver_sql("PRAGMA table_info(simulation_trades)").fetchall()
        }
        if "method_review_json" not in simulation_trade_columns:
            conn.exec_driver_sql("ALTER TABLE simulation_trades ADD COLUMN method_review_json TEXT")
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_simulation_trades_session_id ON simulation_trades(session_id)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_simulation_trades_trade_date ON simulation_trades(trade_date)"
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS simulation_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                trade_date TEXT NOT NULL,
                cash REAL NOT NULL,
                position_qty INTEGER DEFAULT 0,
                avg_price REAL DEFAULT 0,
                evaluation_amount REAL DEFAULT 0,
                total_asset REAL DEFAULT 0,
                unrealized_profit REAL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES simulation_sessions(id)
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_simulation_snapshots_session_id ON simulation_snapshots(session_id)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_simulation_snapshots_trade_date ON simulation_snapshots(trade_date)"
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS simulation_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                review_status TEXT DEFAULT '미복기',
                self_review_text TEXT,
                gpt_prompt_text TEXT,
                gpt_review_text TEXT,
                improvement_point TEXT,
                next_training_goal TEXT,
                main_mistake TEXT,
                discipline_score INTEGER,
                reviewed_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES simulation_sessions(id)
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_simulation_reviews_session_id "
            "ON simulation_reviews(session_id)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_simulation_reviews_status "
            "ON simulation_reviews(review_status)"
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS backtest_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_name TEXT NOT NULL,
                description TEXT,
                trade_method_id INTEGER,
                buy_conditions_json TEXT NOT NULL,
                sell_conditions_json TEXT NOT NULL,
                position_rule_json TEXT NOT NULL,
                fee_rate REAL NOT NULL DEFAULT 0.00015,
                slippage_rate REAL NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_backtest_rules_active ON backtest_rules(is_active)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_backtest_rules_trade_method_id ON backtest_rules(trade_method_id)"
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS backtest_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id INTEGER NOT NULL,
                stock_code TEXT NOT NULL,
                stock_name TEXT,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                initial_cash REAL NOT NULL,
                final_asset REAL,
                total_profit REAL,
                total_return_rate REAL,
                max_drawdown REAL,
                trade_count INTEGER DEFAULT 0,
                win_count INTEGER DEFAULT 0,
                loss_count INTEGER DEFAULT 0,
                breakeven_count INTEGER DEFAULT 0,
                win_rate REAL,
                avg_profit_rate REAL,
                avg_loss_rate REAL,
                profit_factor REAL,
                avg_holding_days REAL,
                total_fee REAL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'completed',
                message TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_backtest_runs_rule_id ON backtest_runs(rule_id)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_backtest_runs_stock_code ON backtest_runs(stock_code)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_backtest_runs_created_at ON backtest_runs(created_at)"
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS backtest_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                buy_date TEXT NOT NULL,
                sell_date TEXT,
                buy_price REAL NOT NULL,
                sell_price REAL,
                quantity INTEGER NOT NULL,
                buy_amount REAL NOT NULL,
                sell_amount REAL,
                fee REAL DEFAULT 0,
                profit REAL,
                profit_rate REAL,
                holding_days INTEGER,
                exit_reason TEXT,
                buy_signal_json TEXT,
                sell_signal_json TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_backtest_trades_run_id ON backtest_trades(run_id)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_backtest_trades_buy_date ON backtest_trades(buy_date)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_backtest_trades_sell_date ON backtest_trades(sell_date)"
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS backtest_equity_curve (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                trade_date TEXT NOT NULL,
                cash REAL NOT NULL,
                position_qty INTEGER NOT NULL DEFAULT 0,
                position_value REAL NOT NULL DEFAULT 0,
                total_asset REAL NOT NULL,
                drawdown_rate REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS analysis_indicators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                indicator_key TEXT NOT NULL UNIQUE,
                indicator_name TEXT NOT NULL,
                description TEXT,
                source_type TEXT NOT NULL,
                source_table TEXT,
                source_column TEXT,
                calculation_formula TEXT,
                calculation_type TEXT,
                parameters_json TEXT,
                required_columns_json TEXT,
                data_type TEXT,
                unit TEXT,
                category TEXT,
                allowed_operators_json TEXT,
                default_operator TEXT,
                default_value_json TEXT,
                example_expressions TEXT,
                is_available_for_rule INTEGER DEFAULT 1,
                is_available_for_llm INTEGER DEFAULT 1,
                is_entry_allowed INTEGER DEFAULT 1,
                is_success_allowed INTEGER DEFAULT 0,
                is_failure_allowed INTEGER DEFAULT 0,
                needs_review_default INTEGER DEFAULT 0,
                execution_supported INTEGER DEFAULT 0,
                execution_status TEXT,
                execution_message TEXT,
                is_active INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_analysis_indicators_active_sort "
            "ON analysis_indicators(is_active, sort_order)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_analysis_indicators_category "
            "ON analysis_indicators(category)"
        )
        analysis_indicator_columns = {
            str(row[1]) for row in conn.exec_driver_sql("PRAGMA table_info(analysis_indicators)").fetchall()
        }
        if "calculation_type" not in analysis_indicator_columns:
            conn.exec_driver_sql("ALTER TABLE analysis_indicators ADD COLUMN calculation_type TEXT")
        if "parameters_json" not in analysis_indicator_columns:
            conn.exec_driver_sql("ALTER TABLE analysis_indicators ADD COLUMN parameters_json TEXT")
        if "execution_supported" not in analysis_indicator_columns:
            conn.exec_driver_sql("ALTER TABLE analysis_indicators ADD COLUMN execution_supported INTEGER DEFAULT 0")
        if "execution_status" not in analysis_indicator_columns:
            conn.exec_driver_sql("ALTER TABLE analysis_indicators ADD COLUMN execution_status TEXT")
        if "execution_message" not in analysis_indicator_columns:
            conn.exec_driver_sql("ALTER TABLE analysis_indicators ADD COLUMN execution_message TEXT")
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS analysis_indicator_aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alias_text TEXT NOT NULL,
                indicator_key TEXT NOT NULL,
                alias_type TEXT,
                match_type TEXT,
                default_operator TEXT,
                default_value_json TEXT,
                default_category TEXT,
                apply_to_samples_default INTEGER DEFAULT 0,
                needs_review INTEGER DEFAULT 1,
                confidence REAL DEFAULT 0.8,
                description TEXT,
                is_active INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(alias_text, indicator_key)
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_analysis_indicator_aliases_indicator_key "
            "ON analysis_indicator_aliases(indicator_key)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_analysis_indicator_aliases_active_sort "
            "ON analysis_indicator_aliases(is_active, sort_order)"
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS analysis_condition_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_key TEXT NOT NULL UNIQUE,
                template_name TEXT NOT NULL,
                description TEXT,
                template_type TEXT,
                condition_json TEXT NOT NULL,
                default_apply_to_samples INTEGER DEFAULT 0,
                needs_review INTEGER DEFAULT 1,
                is_available_for_llm INTEGER DEFAULT 1,
                is_active INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS analysis_indicator_candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT,
                source_text TEXT,
                suggested_indicator_key TEXT NOT NULL,
                suggested_indicator_name TEXT,
                description TEXT,
                calculation_type TEXT,
                formula_description TEXT,
                parameters_json TEXT,
                required_indicators_json TEXT,
                usage_json TEXT,
                lookahead_risk INTEGER DEFAULT 0,
                validation_status TEXT,
                validation_message TEXT,
                execution_supported INTEGER DEFAULT 0,
                execution_status TEXT,
                execution_message TEXT,
                decision_status TEXT DEFAULT 'pending',
                decision_note TEXT,
                linked_indicator_id INTEGER,
                origin_research_run_id INTEGER,
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_analysis_indicator_candidates_status "
            "ON analysis_indicator_candidates(decision_status, validation_status)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_analysis_indicator_candidates_key "
            "ON analysis_indicator_candidates(suggested_indicator_key)"
        )
        analysis_candidate_columns = {
            str(row[1]) for row in conn.exec_driver_sql("PRAGMA table_info(analysis_indicator_candidates)").fetchall()
        }
        if "execution_supported" not in analysis_candidate_columns:
            conn.exec_driver_sql("ALTER TABLE analysis_indicator_candidates ADD COLUMN execution_supported INTEGER DEFAULT 0")
        if "execution_status" not in analysis_candidate_columns:
            conn.exec_driver_sql("ALTER TABLE analysis_indicator_candidates ADD COLUMN execution_status TEXT")
        if "execution_message" not in analysis_candidate_columns:
            conn.exec_driver_sql("ALTER TABLE analysis_indicator_candidates ADD COLUMN execution_message TEXT")
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_analysis_condition_templates_active_sort "
            "ON analysis_condition_templates(is_active, sort_order)"
        )
        for row in DEFAULT_ANALYSIS_INDICATORS:
            conn.exec_driver_sql(
                """
                INSERT OR IGNORE INTO analysis_indicators (
                    indicator_key, indicator_name, description, source_type, source_table, source_column,
                    calculation_formula, calculation_type, parameters_json, required_columns_json, data_type, unit, category, allowed_operators_json,
                    default_operator, default_value_json, example_expressions, is_available_for_rule,
                    is_available_for_llm, is_entry_allowed, is_success_allowed, is_failure_allowed,
                    needs_review_default, execution_supported, execution_status, execution_message, is_active, sort_order, created_at, updated_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """,
                (
                    str(row["indicator_key"]),
                    str(row["indicator_name"]),
                    row.get("description"),
                    str(row.get("source_type") or "calculated"),
                    row.get("source_table"),
                    row.get("source_column"),
                    row.get("calculation_formula"),
                    row.get("calculation_type"),
                    row.get("parameters_json") or json_text({}),
                    row.get("required_columns_json") or json_text([]),
                    row.get("data_type") or "number",
                    row.get("unit"),
                    row.get("category") or "condition",
                    row.get("allowed_operators_json") or json_text(BASE_OPERATORS),
                    row.get("default_operator"),
                    row.get("default_value_json"),
                    row.get("example_expressions"),
                    int(row.get("is_available_for_rule", 1)),
                    int(row.get("is_available_for_llm", 1)),
                    int(row.get("is_entry_allowed", 1)),
                    int(row.get("is_success_allowed", 0)),
                    int(row.get("is_failure_allowed", 0)),
                    int(row.get("needs_review_default", 0)),
                    int(row.get("execution_supported", 1 if row.get("calculation_type") == "distance_pct" else 0)),
                    row.get("execution_status") or ("supported" if row.get("calculation_type") == "distance_pct" else None),
                    row.get("execution_message") or ("distance_pct 계산 유형은 샘플 엔진에서 실행 가능합니다." if row.get("calculation_type") == "distance_pct" else None),
                    int(row.get("is_active", 1)),
                    int(row.get("sort_order", 0)),
                ),
            )
        for row in DEFAULT_ANALYSIS_ALIASES:
            conn.exec_driver_sql(
                """
                INSERT OR IGNORE INTO analysis_indicator_aliases (
                    alias_text, indicator_key, alias_type, match_type, default_operator, default_value_json,
                    default_category, apply_to_samples_default, needs_review, confidence, description,
                    is_active, sort_order, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (
                    str(row["alias_text"]),
                    str(row["indicator_key"]),
                    row.get("alias_type") or "phrase",
                    row.get("match_type") or "contains",
                    row.get("default_operator"),
                    row.get("default_value_json"),
                    row.get("default_category") or "entry_filter",
                    int(row.get("apply_to_samples_default", 0)),
                    int(row.get("needs_review", 1)),
                    float(row.get("confidence", 0.8)),
                    row.get("description"),
                    int(row.get("is_active", 1)),
                    int(row.get("sort_order", 0)),
                ),
            )
        for row in DEFAULT_ANALYSIS_CONDITION_TEMPLATES:
            conn.exec_driver_sql(
                """
                INSERT OR IGNORE INTO analysis_condition_templates (
                    template_key, template_name, description, template_type, condition_json,
                    default_apply_to_samples, needs_review, is_available_for_llm, is_active,
                    sort_order, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (
                    str(row["template_key"]),
                    str(row["template_name"]),
                    row.get("description"),
                    row.get("template_type") or "entry_filter",
                    str(row["condition_json"]),
                    int(row.get("default_apply_to_samples", 0)),
                    int(row.get("needs_review", 1)),
                    int(row.get("is_available_for_llm", 1)),
                    int(row.get("is_active", 1)),
                    int(row.get("sort_order", 0)),
                ),
            )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS pattern_research_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                research_name TEXT,
                stock_codes_json TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                goal_text TEXT,
                parsed_goal_json TEXT,
                target_return_pct REAL,
                target_days INTEGER,
                stop_loss_pct REAL,
                max_holding_days INTEGER,
                summary_json TEXT,
                gpt_prompt_text TEXT,
                gpt_response_text TEXT,
                status TEXT NOT NULL DEFAULT 'completed',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_pattern_research_runs_created_at "
            "ON pattern_research_runs(created_at)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_pattern_research_runs_status "
            "ON pattern_research_runs(status)"
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS pattern_research_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                stock_code TEXT NOT NULL,
                stock_name TEXT,
                trade_date TEXT NOT NULL,
                entry_price REAL,
                max_future_return_pct REAL,
                min_future_return_pct REAL,
                future_return_pct REAL,
                target_hit INTEGER DEFAULT 0,
                stop_hit INTEGER DEFAULT 0,
                result_label TEXT NOT NULL,
                features_json TEXT,
                pattern_tags_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES pattern_research_runs(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_pattern_research_samples_run_id "
            "ON pattern_research_samples(run_id)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_pattern_research_samples_result_label "
            "ON pattern_research_samples(result_label)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_pattern_research_samples_stock_code "
            "ON pattern_research_samples(stock_code)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_pattern_research_samples_trade_date "
            "ON pattern_research_samples(trade_date)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_backtest_equity_curve_run_id ON backtest_equity_curve(run_id)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_backtest_equity_curve_trade_date ON backtest_equity_curve(trade_date)"
        )
        conn.exec_driver_sql(
            """
            INSERT OR IGNORE INTO telegram_sources
            (source_name, channel_username, channel_title, source_type, description, is_active, is_default, is_deleted, created_at, updated_at)
            VALUES
            ('주식급등일보', 'stockdaily_news', '주식급등일보', 'channel', '기본 등록 채널', 1, 1, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
            ('번개맞은 뉴스', 'lightning_news', '번개맞은 뉴스', 'channel', '기본 등록 채널', 1, 1, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_daily_theme_flow_ranks_trade_date "
            "ON daily_theme_flow_ranks(trade_date)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_daily_theme_flow_ranks_market_theme_id "
            "ON daily_theme_flow_ranks(market_theme_id)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_daily_theme_flow_ranks_final_rank "
            "ON daily_theme_flow_ranks(final_rank)"
        )
