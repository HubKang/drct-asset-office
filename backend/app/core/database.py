from __future__ import annotations

from collections.abc import Generator
import hashlib
import json
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.app.core.config import DATABASE_URL, SQLITE_BUSY_TIMEOUT_MS, SQLITE_JOURNAL_MODE, SQLITE_SYNCHRONOUS, KIWOOM_REST_MARKET_KOSPI_CODE, KIWOOM_REST_MARKET_KOSDAQ_CODE, KIWOOM_REST_MARKET_KOSPI_TYPE, KIWOOM_REST_MARKET_KOSDAQ_TYPE
from backend.app.core.market_signal_validation_summary import compact_validation_summary
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


def _ensure_column(conn, table_name: str, column_name: str, column_sql: str) -> None:  # type: ignore[no-untyped-def]
    rows = conn.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()
    existing = {str(row[1]) for row in rows}
    if column_name not in existing:
        conn.exec_driver_sql(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")


def _drop_column_if_exists(conn, table_name: str, column_name: str) -> None:  # type: ignore[no-untyped-def]
    rows = conn.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()
    existing = {str(row[1]) for row in rows}
    if column_name not in existing:
        return
    try:
        conn.exec_driver_sql(f"ALTER TABLE {table_name} DROP COLUMN {column_name}")
    except Exception:
        # Older SQLite versions cannot drop columns. The application no longer
        # reads or writes this legacy preservation column, so leaving it is safe.
        pass


def _telegram_canonical_url(value: str | None) -> str | None:
    raw = (value or "").strip().rstrip(".,;:!?)")
    if not raw:
        return None
    try:
        parts = urlsplit(raw)
        if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
            return None
        host = parts.netloc.lower()
        if host in {"t.me", "telegram.me", "www.t.me"}:
            return None
        query = [(key, val) for key, val in parse_qsl(parts.query, keep_blank_values=True)
                 if not key.lower().startswith("utm_") and key.lower() not in {"fbclid", "gclid", "igshid"}]
        return urlunsplit((parts.scheme.lower(), host, parts.path.rstrip("/") or "/", urlencode(sorted(query)), ""))
    except Exception:
        return None


def _telegram_migration_title(item_title: str | None, message_text: str | None) -> str:
    if (item_title or "").strip():
        return re.sub(r"\s+", " ", str(item_title)).strip()[:180]
    for line in (message_text or "").splitlines():
        clean = re.sub(r"https?://\S+", " ", line, flags=re.IGNORECASE)
        clean = re.sub(r"\s+", " ", clean).strip(" -|⚡🔥✅")
        if len(clean) >= 5:
            return clean[:180]
    return "제목 확인 필요"


def _telegram_fingerprint(message_text: str | None, source_url: str | None, title: str) -> str:
    canonical = _telegram_canonical_url(source_url)
    if canonical:
        source = f"url:{canonical}"
    else:
        normalized = re.sub(r"https?://\S+", " ", message_text or "", flags=re.IGNORECASE)
        normalized = re.sub(r"\s+", " ", normalized).strip().lower() or title.lower()
        source = f"text:{normalized}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _news_canonical_url(value: str | None) -> str | None:
    raw = (value or "").strip().rstrip(".,;:!?)")
    if not raw:
        return None
    try:
        parts = urlsplit(raw)
        if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
            return None
        blocked = {"fbclid", "gclid", "igshid", "mc_cid", "mc_eid"}
        query = [(key, val) for key, val in parse_qsl(parts.query, keep_blank_values=True)
                 if not key.lower().startswith("utm_") and key.lower() not in blocked]
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/") or "/", urlencode(sorted(query)), ""))
    except Exception:
        return None


def _ensure_news_url_is_not_globally_unique(conn) -> None:  # type: ignore[no-untyped-def]
    """Allow one canonical article to be related to multiple stocks."""
    indexes = conn.exec_driver_sql("PRAGMA index_list(news_items)").fetchall()
    has_unique_url = False
    for index in indexes:
        if not bool(index[2]):
            continue
        columns = conn.exec_driver_sql(f"PRAGMA index_info('{index[1]}')").fetchall()
        if [str(column[2]) for column in columns] == ["url"]:
            has_unique_url = True
            break
    if not has_unique_url:
        return

    conn.exec_driver_sql("DROP TABLE IF EXISTS news_items_without_global_url_unique")
    conn.exec_driver_sql("""
        CREATE TABLE news_items_without_global_url_unique (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_id INTEGER,
            title TEXT NOT NULL,
            source TEXT,
            url TEXT,
            article_fingerprint TEXT,
            published_at TEXT,
            collected_at TEXT NOT NULL,
            raw_text_path TEXT,
            summary TEXT,
            sentiment TEXT,
            importance_score INTEGER NOT NULL DEFAULT 0,
            ai_summary TEXT,
            ai_sentiment TEXT,
            ai_importance_score INTEGER DEFAULT 0,
            ai_tags TEXT,
            ai_processed_at TEXT,
            ai_summary_error TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE SET NULL
        )
    """)
    conn.exec_driver_sql("""
        INSERT INTO news_items_without_global_url_unique
        (id, stock_id, title, source, url, article_fingerprint, published_at, collected_at,
         raw_text_path, summary, sentiment, importance_score, ai_summary, ai_sentiment,
         ai_importance_score, ai_tags, ai_processed_at, ai_summary_error, created_at)
        SELECT id,
               CASE WHEN stock_id IS NULL OR EXISTS (SELECT 1 FROM stocks WHERE stocks.id = news_items.stock_id)
                    THEN stock_id ELSE NULL END,
               title, source, url, article_fingerprint, published_at, collected_at,
               raw_text_path, summary, sentiment, importance_score, ai_summary, ai_sentiment,
               ai_importance_score, ai_tags, ai_processed_at, ai_summary_error, created_at
        FROM news_items
    """)
    conn.exec_driver_sql("DROP TABLE news_items")
    conn.exec_driver_sql("ALTER TABLE news_items_without_global_url_unique RENAME TO news_items")


KMS_SETTING_SEEDS: list[tuple[str, str, str, int, list[tuple[str, str, str | None, str | None, str | None, int, int, int]]]] = [
    (
        "PARA_TYPE",
        "PARA 유형",
        "지식의 PARA 분류",
        10,
        [
            ("PROJECT", "진행 과제", "목표가 있는 진행성 지식", "#dbeafe", "P", 10, 0, 1),
            ("AREA", "지속 관리 영역", "반복적으로 관리할 영역", "#dcfce7", "A", 20, 0, 1),
            ("RESOURCE", "참고 자료", "나중에 참고할 자료", "#fef3c7", "R", 30, 1, 1),
            ("ARCHIVE", "보관", "현재는 비활성인 보관 지식", "#e5e7eb", "AR", 40, 0, 1),
        ],
    ),
    (
        "KNOWLEDGE_CATEGORY",
        "지식 카테고리",
        "KMS 지식 분류",
        20,
        [
            ("UNCATEGORIZED", "미분류", None, "#f1f5f9", None, 10, 1, 1),
            ("MARKET", "시장", None, "#dbeafe", None, 20, 0, 1),
            ("MATERIAL", "재료", None, "#ffedd5", None, 30, 0, 1),
            ("SUPPLY", "수급", None, "#ede9fe", None, 40, 0, 1),
            ("CHART", "차트", None, "#dcfce7", None, 50, 0, 1),
            ("FINANCE", "재무", None, "#cffafe", None, 60, 0, 1),
            ("METHOD", "기법", None, "#e0e7ff", None, 70, 0, 1),
            ("PSYCHOLOGY", "심리", None, "#fce7f3", None, 80, 0, 1),
            ("RISK", "리스크", None, "#fee2e2", None, 90, 0, 1),
        ],
    ),
    (
        "KNOWLEDGE_STATUS",
        "지식 상태",
        "지식 정리 및 활용 상태",
        30,
        [
            ("COLLECTED", "수집됨", None, "#e0f2fe", None, 10, 1, 1),
            ("ORGANIZED", "정리됨", None, "#dcfce7", None, 20, 0, 1),
            ("VERIFYING", "검증중", None, "#fef3c7", None, 30, 0, 1),
            ("APPLIED", "적용됨", None, "#ede9fe", None, 40, 0, 1),
            ("ARCHIVED", "보관", None, "#e5e7eb", None, 50, 0, 1),
        ],
    ),
    (
        "IMPORTANCE_LEVEL",
        "중요도",
        "지식 중요도",
        40,
        [
            ("LOW", "낮음", None, "#f1f5f9", None, 10, 0, 1),
            ("NORMAL", "보통", None, "#dbeafe", None, 20, 1, 1),
            ("HIGH", "높음", None, "#fef3c7", None, 30, 0, 1),
            ("CORE", "핵심", None, "#fee2e2", None, 40, 0, 1),
        ],
    ),
    (
        "TAG_TYPE",
        "태그 유형",
        "수동/AI 태그 유형",
        50,
        [
            ("CONCEPT", "개념", None, "#e0f2fe", None, 10, 1, 1),
            ("MARKET", "시장", None, "#dbeafe", None, 20, 0, 1),
            ("THEME", "테마", None, "#ede9fe", None, 30, 0, 1),
            ("STOCK", "종목", None, "#dcfce7", None, 40, 0, 1),
            ("INDICATOR", "지표", None, "#cffafe", None, 50, 0, 1),
            ("TRADE_METHOD", "매매기법", None, "#e0e7ff", None, 60, 0, 1),
            ("RISK", "리스크", None, "#fee2e2", None, 70, 0, 1),
            ("PSYCHOLOGY", "심리", None, "#fce7f3", None, 80, 0, 1),
            ("SCREEN", "화면", None, "#f1f5f9", None, 90, 0, 1),
        ],
    ),
    (
        "USAGE_CONTEXT",
        "사용처",
        "지식 활용 맥락",
        60,
        [
            ("UNSPECIFIED", "미지정", None, "#f1f5f9", None, 10, 1, 1),
            ("MARKET_JUDGMENT", "시장판단", None, "#dbeafe", None, 20, 0, 1),
            ("STOCK_ANALYSIS", "종목분석", None, "#dcfce7", None, 30, 0, 1),
            ("THEME_ANALYSIS", "테마분석", None, "#ede9fe", None, 40, 0, 1),
            ("TRADE_TRAINING", "매매훈련", None, "#e0e7ff", None, 50, 0, 1),
            ("PATTERN_RESEARCH", "패턴연구", None, "#fef3c7", None, 60, 0, 1),
            ("RISK_CHECK", "리스크점검", None, "#fee2e2", None, 70, 0, 1),
            ("GPT_JUDGMENT", "GPT판단", None, "#cffafe", None, 80, 0, 1),
        ],
    ),
    (
        "SOURCE_TYPE",
        "출처 유형",
        "지식 출처 유형",
        70,
        [
            ("MANUAL", "직접작성", None, "#dbeafe", None, 10, 1, 1),
            ("NEWS", "기사", None, "#e0f2fe", None, 20, 0, 1),
            ("YOUTUBE", "유튜브", None, "#fee2e2", None, 30, 0, 1),
            ("REPORT", "리포트", None, "#ede9fe", None, 40, 0, 1),
            ("BOOK", "책", None, "#fef3c7", None, 50, 0, 1),
            ("PAPER", "논문", None, "#dcfce7", None, 60, 0, 1),
            ("SYSTEM", "시스템생성", None, "#e5e7eb", None, 70, 0, 1),
        ],
    ),
]


def _seed_kms_settings(conn) -> None:  # type: ignore[no-untyped-def]
    for group_code, group_name, description, sort_order, items in KMS_SETTING_SEEDS:
        conn.exec_driver_sql(
            """
            INSERT OR IGNORE INTO kms_setting_groups
            (group_code, group_name, description, sort_order, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (group_code, group_name, description, sort_order),
        )
        group_id = conn.exec_driver_sql(
            "SELECT id FROM kms_setting_groups WHERE group_code = ?",
            (group_code,),
        ).scalar()
        for item_code, item_name, item_description, color, icon, item_order, is_default, is_system in items:
            conn.exec_driver_sql(
                """
                INSERT OR IGNORE INTO kms_setting_items
                (group_id, item_code, item_name, description, color, icon, sort_order, is_default, is_system, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (group_id, item_code, item_name, item_description, color, icon, item_order, is_default, is_system),
            )


def ensure_runtime_schema() -> None:
    if not DATABASE_URL.startswith("sqlite"):
        return

    with engine.begin() as conn:
        news_columns = {str(row[1]) for row in conn.exec_driver_sql("PRAGMA table_info(news_items)").fetchall()}
        news_v2_migration_needed = bool(news_columns) and "article_fingerprint" not in news_columns
        if news_columns:
            _ensure_column(conn, "news_items", "article_fingerprint", "TEXT")
            if news_v2_migration_needed:
                rows = conn.exec_driver_sql("SELECT id, url FROM news_items WHERE url IS NOT NULL").fetchall()
                for news_id, raw_url in rows:
                    canonical = _news_canonical_url(raw_url)
                    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest() if canonical else None
                    conn.exec_driver_sql(
                        "UPDATE news_items SET article_fingerprint = ? WHERE id = ?",
                        (fingerprint, news_id),
                    )
                conn.exec_driver_sql("""
                    UPDATE news_items
                    SET summary = CASE
                        WHEN ai_summary IS NOT NULL AND trim(ai_summary) <> '' THEN ai_summary
                        ELSE NULL
                    END,
                    raw_text_path = NULL
                """)
            conn.exec_driver_sql("UPDATE news_items SET source = NULL WHERE source = 'naver_news'")
            _ensure_news_url_is_not_globally_unique(conn)
            conn.exec_driver_sql("""
                CREATE INDEX IF NOT EXISTS ix_news_items_stock_fingerprint
                ON news_items(stock_id, article_fingerprint)
                WHERE article_fingerprint IS NOT NULL
            """)
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS news_item_exclusions (
                target_date TEXT NOT NULL,
                stock_id INTEGER NOT NULL,
                article_fingerprint TEXT NOT NULL,
                PRIMARY KEY (target_date, stock_id, article_fingerprint)
            )
        """)
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS news_collection_cursors (
                stock_id INTEGER PRIMARY KEY,
                last_completed_date TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
            )
        """)
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS stock_disclosure_collection_states (
                stock_id INTEGER PRIMARY KEY,
                last_successful_collection_date TEXT NOT NULL,
                last_successful_at TEXT NOT NULL,
                FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
            )
        """)
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS disclosure_item_exclusions (
                exclusion_date TEXT NOT NULL,
                stock_id INTEGER NOT NULL,
                rcept_no TEXT NOT NULL,
                PRIMARY KEY (exclusion_date, stock_id, rcept_no),
                FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
            )
        """)
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_disclosure_exclusions_stock_date ON disclosure_item_exclusions(stock_id, exclusion_date)")
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS us_stocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL, name TEXT, name_ko TEXT,
                exchange TEXT NOT NULL, stock_type TEXT NOT NULL DEFAULT 'COMMON', naver_code TEXT,
                is_active INTEGER NOT NULL DEFAULT 1, last_synced_at TEXT,
                historical_price_status TEXT NOT NULL DEFAULT 'NOT_COLLECTED', historical_price_completed_at TEXT,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(symbol, exchange)
            )
        """)
        _ensure_column(conn, "us_stocks", "historical_price_status", "TEXT NOT NULL DEFAULT 'NOT_COLLECTED'")
        _ensure_column(conn, "us_stocks", "historical_price_completed_at", "TEXT")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_us_stocks_active_type ON us_stocks(is_active, stock_type)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_us_stocks_exchange ON us_stocks(exchange)")
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS us_theme_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, description TEXT,
                sort_order INTEGER NOT NULL DEFAULT 100, active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )
        """)
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS us_themes (
                id INTEGER PRIMARY KEY AUTOINCREMENT, theme_group_id INTEGER NOT NULL, name TEXT NOT NULL,
                description TEXT, keywords TEXT NOT NULL DEFAULT '', sort_order INTEGER NOT NULL DEFAULT 100,
                active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                UNIQUE(theme_group_id, name), FOREIGN KEY(theme_group_id) REFERENCES us_theme_groups(id) ON DELETE RESTRICT
            )
        """)
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS us_theme_stocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT, theme_id INTEGER NOT NULL, us_stock_id INTEGER NOT NULL,
                role TEXT NOT NULL DEFAULT 'RELATED' CHECK(role IN ('LEADER','CORE','RELATED','ETF')),
                is_representative INTEGER NOT NULL DEFAULT 0, sort_order INTEGER NOT NULL DEFAULT 100,
                active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                UNIQUE(theme_id, us_stock_id), FOREIGN KEY(theme_id) REFERENCES us_themes(id) ON DELETE CASCADE,
                FOREIGN KEY(us_stock_id) REFERENCES us_stocks(id) ON DELETE RESTRICT
            )
        """)
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_us_themes_group_active ON us_themes(theme_group_id, active)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_us_theme_stocks_theme_active ON us_theme_stocks(theme_id, active)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_us_theme_stocks_stock_active ON us_theme_stocks(us_stock_id, active)")
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS us_stock_daily_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT, us_stock_id INTEGER NOT NULL, trade_date TEXT NOT NULL,
                open_price REAL NOT NULL, high_price REAL NOT NULL, low_price REAL NOT NULL, close_price REAL NOT NULL,
                volume INTEGER NOT NULL DEFAULT 0, source TEXT NOT NULL DEFAULT 'KIWOOM', collected_at TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(us_stock_id, trade_date),
                FOREIGN KEY(us_stock_id) REFERENCES us_stocks(id) ON DELETE CASCADE
            )
        """)
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_us_stock_daily_prices_date ON us_stock_daily_prices(trade_date)")
        conn.exec_driver_sql("""
            UPDATE us_stocks
            SET historical_price_status='COMPLETE',
                historical_price_completed_at=COALESCE(historical_price_completed_at,last_synced_at,updated_at)
            WHERE historical_price_status='NOT_COLLECTED'
              AND EXISTS (SELECT 1 FROM us_stock_daily_prices p WHERE p.us_stock_id=us_stocks.id)
        """)
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS us_theme_daily_returns (
                id INTEGER PRIMARY KEY AUTOINCREMENT, theme_id INTEGER NOT NULL, trade_date TEXT NOT NULL,
                simple_return REAL NOT NULL, theme_strength REAL NOT NULL, trimmed_mean_return REAL NOT NULL,
                median_return REAL NOT NULL, breadth_ratio REAL NOT NULL, valid_stock_count INTEGER NOT NULL,
                up_count INTEGER NOT NULL, down_count INTEGER NOT NULL, flat_count INTEGER NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(theme_id, trade_date),
                FOREIGN KEY(theme_id) REFERENCES us_themes(id) ON DELETE CASCADE
            )
        """)
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_us_theme_daily_returns_date ON us_theme_daily_returns(trade_date)")
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS us_kr_theme_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                us_theme_id INTEGER NOT NULL UNIQUE,
                kr_theme_id INTEGER NOT NULL UNIQUE,
                memo TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(us_theme_id) REFERENCES us_themes(id) ON DELETE RESTRICT,
                FOREIGN KEY(kr_theme_id) REFERENCES market_themes(id) ON DELETE RESTRICT
            )
        """)
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_us_kr_theme_links_active ON us_kr_theme_links(active)")
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS chart_marker_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, description TEXT,
                color TEXT NOT NULL DEFAULT '#64748b', sort_order INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS chart_markers (
                id INTEGER PRIMARY KEY AUTOINCREMENT, marker_group_id INTEGER NOT NULL, name TEXT NOT NULL,
                description TEXT, symbol TEXT NOT NULL DEFAULT '◆', sort_order INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(marker_group_id, name),
                FOREIGN KEY(marker_group_id) REFERENCES chart_marker_groups(id) ON DELETE RESTRICT
            )
        """)
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS chart_marker_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, stock_id INTEGER NOT NULL, marker_id INTEGER NOT NULL,
                marker_date TEXT NOT NULL, memo TEXT, review_result TEXT, reviewed_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(stock_id, marker_id, marker_date),
                CHECK(review_result IS NULL OR review_result IN ('SUCCESS', 'FAILURE')),
                FOREIGN KEY(stock_id) REFERENCES stocks(id) ON DELETE CASCADE,
                FOREIGN KEY(marker_id) REFERENCES chart_markers(id) ON DELETE RESTRICT
            )
        """)
        _ensure_column(conn, "chart_marker_events", "review_result", "TEXT")
        _ensure_column(conn, "chart_marker_events", "reviewed_at", "TEXT")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_chart_marker_events_stock_date ON chart_marker_events(stock_id, marker_date)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_chart_marker_events_marker_stock_date ON chart_marker_events(marker_id, stock_id, marker_date DESC)")
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS app_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT NOT NULL,
                owner_type TEXT,
                owner_id INTEGER,
                original_file_name TEXT NOT NULL,
                stored_file_name TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                file_url TEXT NOT NULL,
                file_ext TEXT NOT NULL,
                mime_type TEXT,
                file_size INTEGER NOT NULL,
                width INTEGER,
                height INTEGER,
                sort_order INTEGER NOT NULL DEFAULT 0,
                description TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_app_images_domain_owner ON app_images(domain, owner_type, owner_id, is_active)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_app_images_domain_created ON app_images(domain, created_at)"
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS trade_training_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                initial_capital REAL NOT NULL,
                cash_balance REAL NOT NULL,
                realized_equity REAL NOT NULL,
                commission_rate REAL NOT NULL DEFAULT 0.001,
                risk_per_trade_pct REAL NOT NULL DEFAULT 1.0,
                max_open_risk_pct REAL NOT NULL DEFAULT 3.0,
                max_position_count INTEGER NOT NULL DEFAULT 5,
                display_days_default INTEGER NOT NULL DEFAULT 80,
                moving_average_periods_default TEXT NOT NULL DEFAULT '[5,10,20,60,120]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_trade_training_accounts_status ON trade_training_accounts(status)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_trade_training_accounts_updated ON trade_training_accounts(updated_at)"
        )
        rows = conn.exec_driver_sql("PRAGMA table_info(watchlist)").fetchall()
        if not rows:
            return

        columns = {str(row[1]) for row in rows}
        if "is_active" not in columns:
            conn.exec_driver_sql("ALTER TABLE watchlist ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")

        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS watchlist_evaluation_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_date TEXT NOT NULL,
                run_type TEXT NOT NULL DEFAULT 'MANUAL',
                status TEXT NOT NULL DEFAULT 'SUCCESS',
                memo TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS watchlist_evaluation_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                watchlist_stock_id INTEGER NOT NULL,
                stock_id INTEGER NOT NULL,
                evaluated_at TEXT NOT NULL,
                market_score REAL,
                material_score REAL,
                supply_score REAL,
                chart_score REAL,
                financial_score REAL,
                total_score REAL,
                market_status TEXT,
                material_status TEXT,
                supply_status TEXT,
                chart_status TEXT,
                financial_status TEXT,
                overall_status TEXT,
                data_confidence TEXT NOT NULL DEFAULT 'NOT_EVALUATED',
                risk_flags_json TEXT NOT NULL DEFAULT '[]',
                missing_data_json TEXT NOT NULL DEFAULT '[]',
                summary_text TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES watchlist_evaluation_runs(id) ON DELETE CASCADE,
                FOREIGN KEY (watchlist_stock_id) REFERENCES watchlist(id) ON DELETE CASCADE,
                FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS watchlist_evaluation_factors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                score_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                factor_code TEXT NOT NULL,
                factor_name TEXT NOT NULL,
                raw_value TEXT,
                normalized_score REAL,
                weight REAL,
                contribution_score REAL,
                reason TEXT,
                source_table TEXT,
                source_date TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (score_id) REFERENCES watchlist_evaluation_scores(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_watchlist_evaluation_scores_watchlist ON watchlist_evaluation_scores(watchlist_stock_id, evaluated_at)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_watchlist_evaluation_scores_run ON watchlist_evaluation_scores(run_id)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_watchlist_evaluation_factors_score ON watchlist_evaluation_factors(score_id)"
        )

        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS stock_financial_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT, stock_id INTEGER NOT NULL, stock_code TEXT NOT NULL,
                snapshot_date TEXT NOT NULL, source_type TEXT NOT NULL, source_method TEXT NOT NULL,
                current_price REAL, market_cap INTEGER, listed_shares INTEGER, per REAL, pbr REAL, eps REAL, bps REAL,
                roe REAL, debt_ratio REAL, reserve_ratio REAL, operating_margin REAL, net_margin REAL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                UNIQUE(stock_id, snapshot_date, source_method), FOREIGN KEY(stock_id) REFERENCES stocks(id) ON DELETE CASCADE
            )
        """)
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_stock_financial_snapshots_stock_date ON stock_financial_snapshots(stock_id, snapshot_date)")
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS stock_financial_statements (
                id INTEGER PRIMARY KEY AUTOINCREMENT, stock_id INTEGER NOT NULL, stock_code TEXT NOT NULL,
                statement_type TEXT NOT NULL, fiscal_year INTEGER NOT NULL, fiscal_quarter INTEGER NOT NULL DEFAULT 0,
                period_label TEXT NOT NULL, period_end_date TEXT, source_type TEXT NOT NULL, source_method TEXT NOT NULL,
                revenue INTEGER, operating_profit INTEGER, net_income INTEGER, total_assets INTEGER, total_liabilities INTEGER,
                total_equity INTEGER, operating_cash_flow INTEGER, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                UNIQUE(stock_id, statement_type, fiscal_year, fiscal_quarter, source_method), FOREIGN KEY(stock_id) REFERENCES stocks(id) ON DELETE CASCADE
            )
        """)
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_stock_financial_statements_stock_period ON stock_financial_statements(stock_id, statement_type, fiscal_year, fiscal_quarter)")
        financial_statement_columns = {str(row[1]) for row in conn.exec_driver_sql("PRAGMA table_info(stock_financial_statements)").fetchall()}
        financial_statement_add_columns = {
            "value_type": "TEXT",
            "calculation_method": "TEXT",
            "source_report_code": "TEXT",
            "source_period_label": "TEXT",
            "report_code": "TEXT",
        }
        for column_name, column_def in financial_statement_add_columns.items():
            if column_name not in financial_statement_columns:
                conn.exec_driver_sql(f"ALTER TABLE stock_financial_statements ADD COLUMN {column_name} {column_def}")
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS stock_external_identifiers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_id INTEGER NOT NULL,
                stock_code TEXT NOT NULL,
                corp_code TEXT NOT NULL,
                corp_name TEXT,
                source_type TEXT NOT NULL,
                source_method TEXT NOT NULL,
                mapped_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(stock_code, source_type),
                FOREIGN KEY(stock_id) REFERENCES stocks(id) ON DELETE CASCADE
            )
        """)
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_stock_external_identifiers_stock ON stock_external_identifiers(stock_id, source_type)")
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS stock_shareholder_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_id INTEGER NOT NULL,
                stock_code TEXT NOT NULL,
                snapshot_date TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_method TEXT NOT NULL,
                report_code TEXT,
                receipt_no TEXT,
                largest_shareholder_name TEXT,
                largest_shareholder_shares INTEGER,
                largest_shareholder_ratio REAL,
                major_shareholder_name TEXT,
                major_shareholder_shares INTEGER,
                major_shareholder_ratio REAL,
                ownership_change_flag INTEGER,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(stock_id, snapshot_date, source_method),
                FOREIGN KEY(stock_id) REFERENCES stocks(id) ON DELETE CASCADE
            )
        """)
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_stock_shareholder_snapshots_stock_date ON stock_shareholder_snapshots(stock_id, snapshot_date)")
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS stock_shareholder_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_id INTEGER NOT NULL,
                stock_code TEXT NOT NULL,
                report_date TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_method TEXT NOT NULL,
                report_type TEXT,
                receipt_no TEXT,
                reporter_name TEXT,
                shares INTEGER,
                ratio REAL,
                previous_ratio REAL,
                change_flag INTEGER,
                reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(stock_id, report_date, source_method, receipt_no),
                FOREIGN KEY(stock_id) REFERENCES stocks(id) ON DELETE CASCADE
            )
        """)
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_stock_shareholder_changes_stock_date ON stock_shareholder_changes(stock_id, report_date)")

        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS stock_investor_flows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_id INTEGER NOT NULL,
                stock_code TEXT NOT NULL,
                flow_date TEXT NOT NULL,
                individual_buy_qty INTEGER,
                individual_sell_qty INTEGER,
                individual_net_qty INTEGER,
                individual_buy_amount INTEGER,
                individual_sell_amount INTEGER,
                individual_net_amount INTEGER,
                foreign_buy_qty INTEGER,
                foreign_sell_qty INTEGER,
                foreign_net_qty INTEGER,
                foreign_buy_amount INTEGER,
                foreign_sell_amount INTEGER,
                foreign_net_amount INTEGER,
                foreign_holding_qty INTEGER,
                foreign_holding_ratio REAL,
                institution_buy_qty INTEGER,
                institution_sell_qty INTEGER,
                institution_net_qty INTEGER,
                institution_buy_amount INTEGER,
                institution_sell_amount INTEGER,
                institution_net_amount INTEGER,
                financial_investment_net_qty INTEGER,
                insurance_net_qty INTEGER,
                investment_trust_net_qty INTEGER,
                bank_net_qty INTEGER,
                other_finance_net_qty INTEGER,
                pension_fund_net_qty INTEGER,
                private_fund_net_qty INTEGER,
                other_corporation_net_qty INTEGER,
                program_buy_qty INTEGER,
                program_sell_qty INTEGER,
                program_net_qty INTEGER,
                program_buy_amount INTEGER,
                program_sell_amount INTEGER,
                program_net_amount INTEGER,
                program_arbitrage_net_qty INTEGER,
                program_non_arbitrage_net_qty INTEGER,
                source TEXT NOT NULL DEFAULT 'derived_price_flow',
                data_source_type TEXT NOT NULL DEFAULT 'DERIVED_PRICE_FLOW',
                source_method TEXT NOT NULL DEFAULT 'derived_price_flow',
                is_real_investor_flow INTEGER NOT NULL DEFAULT 0,
                collection_status TEXT NOT NULL DEFAULT 'SUCCESS',
                raw_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
            )            """
        )
        investor_flow_columns = {str(row[1]) for row in conn.exec_driver_sql("PRAGMA table_info(stock_investor_flows)").fetchall()}
        investor_flow_add_columns = {
            "individual_buy_qty": "INTEGER",
            "individual_sell_qty": "INTEGER",
            "individual_net_qty": "INTEGER",
            "individual_buy_amount": "INTEGER",
            "individual_sell_amount": "INTEGER",
            "individual_net_amount": "INTEGER",
            "foreign_holding_qty": "INTEGER",
            "foreign_holding_ratio": "REAL",
            "data_source_type": "TEXT NOT NULL DEFAULT 'DERIVED_PRICE_FLOW'",
            "source_method": "TEXT NOT NULL DEFAULT 'derived_price_flow'",
            "is_real_investor_flow": "INTEGER NOT NULL DEFAULT 0",
        }
        for column_name, column_def in investor_flow_add_columns.items():
            if column_name not in investor_flow_columns:
                conn.exec_driver_sql(f"ALTER TABLE stock_investor_flows ADD COLUMN {column_name} {column_def}")
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_stock_investor_flows_stock_date ON stock_investor_flows(stock_id, flow_date)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_stock_investor_flows_stock_date ON stock_investor_flows(stock_id, flow_date)"
        )
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
            CREATE TABLE IF NOT EXISTS market_index_provider_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                index_code TEXT NOT NULL,
                provider TEXT NOT NULL DEFAULT 'KIWOOM_REST',
                api_type TEXT,
                provider_symbol TEXT,
                market_type TEXT,
                indicator_type TEXT,
                request_params_json TEXT,
                api_id TEXT,
                endpoint_url TEXT,
                is_enabled INTEGER NOT NULL DEFAULT 0,
                is_verified INTEGER NOT NULL DEFAULT 0,
                verified_at TEXT,
                last_test_status TEXT,
                last_test_message TEXT,
                last_tested_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(index_code, provider),
                FOREIGN KEY (index_code) REFERENCES market_indexes(index_code) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_index_provider_mappings_index "
            "ON market_index_provider_mappings(index_code, provider)"
        )
        mapping_columns = {str(row[1]) for row in conn.exec_driver_sql("PRAGMA table_info(market_index_provider_mappings)").fetchall()}
        if "api_id" not in mapping_columns:
            conn.exec_driver_sql("ALTER TABLE market_index_provider_mappings ADD COLUMN api_id TEXT")
        if "endpoint_url" not in mapping_columns:
            conn.exec_driver_sql("ALTER TABLE market_index_provider_mappings ADD COLUMN endpoint_url TEXT")
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_index_provider_mappings_enabled "
            "ON market_index_provider_mappings(provider, is_enabled, is_verified)"
        )

        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_index_provider_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL DEFAULT 'KIWOOM_REST',
                market_type TEXT NOT NULL,
                market_code TEXT,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                group_name TEXT,
                source_api_id TEXT NOT NULL DEFAULT 'ka10101',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(provider, market_type, code)
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_index_provider_codes_market "
            "ON market_index_provider_codes(provider, market_type, code)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_index_provider_codes_name "
            "ON market_index_provider_codes(provider, name)"
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
            ('KOSPI', '코스피', '국내대표지수', 'KOSPI', 'KRW', 'KIWOOM_REST', 'KOSPI', '한국거래소 유가증권시장 대표 지수', 1, 1),
            ('KOSDAQ', '코스닥', '국내대표지수', 'KOSDAQ', 'KRW', 'KIWOOM_REST', 'KOSDAQ', '한국거래소 코스닥시장 대표 지수', 1, 2),
            ('KOSPI200', '코스피200', '국내보조지수', 'KOSPI', 'KRW', 'KIWOOM_REST', None, '코스피200 보조지수. 키움 provider mapping 확인 필요', 1, 3),
            ('KOSDAQ150', '코스닥150', '국내보조지수', 'KOSDAQ', 'KRW', 'KIWOOM_REST', None, '코스닥150 보조지수. 키움 provider mapping 확인 필요', 1, 4),
            ('KRX100', 'KRX100', '국내보조지수', 'KRX', 'KRW', 'KIWOOM_REST', None, 'KRX100 보조지수. 키움 provider mapping 확인 필요', 1, 5),
            ('KOSPI_ELECTRONICS', '코스피 전기전자', '업종지수', 'KOSPI', 'KRW', 'KIWOOM_REST', None, '코스피 전기전자 업종지수. 키움 provider mapping 확인 필요', 1, 10),
            ('KOSPI_PHARMA', '코스피 의약품', '업종지수', 'KOSPI', 'KRW', 'KIWOOM_REST', None, '코스피 의약품 업종지수. 키움 provider mapping 확인 필요', 1, 11),
            ('KOSPI_CHEMICAL', '코스피 화학', '업종지수', 'KOSPI', 'KRW', 'KIWOOM_REST', None, '코스피 화학 업종지수. 키움 provider mapping 확인 필요', 1, 12),
            ('KOSPI_MACHINERY', '코스피 기계', '업종지수', 'KOSPI', 'KRW', 'KIWOOM_REST', None, '코스피 기계 업종지수. 키움 provider mapping 확인 필요', 1, 13),
            ('KOSPI_TRANSPORT_EQUIPMENT', '코스피 운수장비', '업종지수', 'KOSPI', 'KRW', 'KIWOOM_REST', None, '코스피 운수장비 업종지수. 키움 provider mapping 확인 필요', 1, 14),
            ('KOSPI_STEEL_METAL', '코스피 철강금속', '업종지수', 'KOSPI', 'KRW', 'KIWOOM_REST', None, '코스피 철강금속 업종지수. 키움 provider mapping 확인 필요', 1, 15),
            ('KOSPI_FINANCE', '코스피 금융업', '업종지수', 'KOSPI', 'KRW', 'KIWOOM_REST', None, '코스피 금융업 업종지수. 키움 provider mapping 확인 필요', 1, 16),
            ('KOSPI_CONSTRUCTION', '코스피 건설업', '업종지수', 'KOSPI', 'KRW', 'KIWOOM_REST', None, '코스피 건설업 업종지수. 키움 provider mapping 확인 필요', 1, 17),
            ('KOSPI_TRANSPORT_WAREHOUSE', '코스피 운수창고', '업종지수', 'KOSPI', 'KRW', 'KIWOOM_REST', None, '코스피 운수창고 업종지수. 키움 provider mapping 확인 필요', 1, 18),
            ('KOSPI_SERVICE', '코스피 서비스업', '업종지수', 'KOSPI', 'KRW', 'KIWOOM_REST', None, '코스피 서비스업 업종지수. 키움 provider mapping 확인 필요', 1, 19),
            ('KOSDAQ_SEMICONDUCTOR', '코스닥 반도체', '업종지수', 'KOSDAQ', 'KRW', 'KIWOOM_REST', None, '코스닥 반도체 업종지수. 키움 provider mapping 확인 필요', 1, 30),
            ('KOSDAQ_IT_HW', '코스닥 IT H/W', '업종지수', 'KOSDAQ', 'KRW', 'KIWOOM_REST', None, '코스닥 IT H/W 업종지수. 키움 provider mapping 확인 필요', 1, 31),
            ('KOSDAQ_IT_SW_SVC', '코스닥 IT S/W & SVC', '업종지수', 'KOSDAQ', 'KRW', 'KIWOOM_REST', None, '코스닥 IT S/W & SVC 업종지수. 키움 provider mapping 확인 필요', 1, 32),
            ('KOSDAQ_PHARMA', '코스닥 제약', '업종지수', 'KOSDAQ', 'KRW', 'KIWOOM_REST', None, '코스닥 제약 업종지수. 키움 provider mapping 확인 필요', 1, 33),
            ('KOSDAQ_GENERAL_ELECTRONICS', '코스닥 일반전기전자', '업종지수', 'KOSDAQ', 'KRW', 'KIWOOM_REST', None, '코스닥 일반전기전자 업종지수. 키움 provider mapping 확인 필요', 1, 34),
            ('KOSDAQ_MACHINE_EQUIPMENT', '코스닥 기계·장비', '업종지수', 'KOSDAQ', 'KRW', 'KIWOOM_REST', None, '코스닥 기계·장비 업종지수. 키움 provider mapping 확인 필요', 1, 35),
            ('KOSDAQ_CHEMICAL', '코스닥 화학', '업종지수', 'KOSDAQ', 'KRW', 'KIWOOM_REST', None, '코스닥 화학 업종지수. 키움 provider mapping 확인 필요', 1, 36),
            ('KOSDAQ_MEDICAL_PRECISION', '코스닥 의료·정밀기기', '업종지수', 'KOSDAQ', 'KRW', 'KIWOOM_REST', None, '코스닥 의료·정밀기기 업종지수. 키움 provider mapping 확인 필요', 1, 37),
            ('GOLD_KRX', 'KRX 금 현물', '금현물', 'KRX', 'KRW', 'KIWOOM_REST', None, 'KRX 금 현물. 키움 provider mapping 확인 필요', 1, 50),        ):
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

        provider_mapping_rows = (
            ("KOSPI", "KIWOOM_REST", "MARKET_INDEX_DAILY", KIWOOM_REST_MARKET_KOSPI_CODE, KIWOOM_REST_MARKET_KOSPI_TYPE, "국내대표지수", '{"inds_cd":"001"}', "ka20006", "/api/dostk/chart", 1, 1, "SUCCESS", None),
            ("KOSDAQ", "KIWOOM_REST", "MARKET_INDEX_DAILY", KIWOOM_REST_MARKET_KOSDAQ_CODE, KIWOOM_REST_MARKET_KOSDAQ_TYPE, "국내대표지수", '{"inds_cd":"101"}', "ka20006", "/api/dostk/chart", 1, 1, "SUCCESS", None),
            ("KOSPI200", "KIWOOM_REST", "MARKET_INDEX_DAILY", "201", "2", "국내보조지수", '{"inds_cd":"201"}', "ka20006", "/api/dostk/chart", 0, 0, "WAITING", "provider mapping은 설정되었지만 아직 검증되지 않았습니다."),
            ("KRX100", "KIWOOM_REST", "MARKET_INDEX_DAILY", "701", "7", "국내보조지수", '{"inds_cd":"701"}', "ka20006", "/api/dostk/chart", 0, 0, "WAITING", "provider mapping은 설정되었지만 아직 검증되지 않았습니다."),
            ("GOLD_KRX", "KIWOOM_REST", "GOLD_SPOT_DAILY", "M04020000", "KRX", "금현물", '{"stk_cd":"M04020000","upd_stkpc_tp":"1"}', "ka50081", "/api/dostk/chart", 0, 0, "WAITING", "provider mapping은 설정되었지만 아직 검증되지 않았습니다."),
        )
        for row in provider_mapping_rows:
            conn.exec_driver_sql(
                """
                INSERT OR IGNORE INTO market_index_provider_mappings
                (index_code, provider, api_type, provider_symbol, market_type, indicator_type, request_params_json,
                 api_id, endpoint_url, is_enabled, is_verified, verified_at, last_test_status, last_test_message, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                row,
            )
            conn.exec_driver_sql(
                """
                UPDATE market_index_provider_mappings
                SET api_type = ?, provider_symbol = ?, market_type = ?, indicator_type = ?, request_params_json = ?,
                    api_id = ?, endpoint_url = ?,
                    is_enabled = CASE WHEN ? = 1 THEN 1 ELSE is_enabled END,
                    is_verified = CASE WHEN ? = 1 THEN 1 ELSE is_verified END,
                    verified_at = CASE WHEN ? = 1 AND verified_at IS NULL THEN CURRENT_TIMESTAMP ELSE verified_at END,
                    last_test_status = CASE WHEN ? = 1 THEN ? WHEN is_verified = 1 THEN last_test_status ELSE COALESCE(last_test_status, ?) END,
                    last_test_message = CASE WHEN ? = 1 THEN ? WHEN is_verified = 1 THEN last_test_message ELSE COALESCE(last_test_message, ?) END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE index_code = ? AND provider = ?
                """,
                (row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9], row[10], row[10], row[10], row[11], row[11], row[10], row[12], row[12], row[0], row[1]),
            )

        conn.exec_driver_sql(
            """
            INSERT OR IGNORE INTO market_index_provider_mappings
            (index_code, provider, api_type, provider_symbol, market_type, indicator_type, request_params_json,
             api_id, endpoint_url, is_enabled, is_verified, last_test_status, last_test_message, created_at, updated_at)
            SELECT index_code, provider,
                   CASE
                       WHEN category = '업종지수' THEN 'SECTOR_INDEX'
                       WHEN category = '금현물' THEN 'GOLD_SPOT'
                       ELSE 'MARKET_INDEX'
                   END,
                   NULL, market, category, '{}',
                   CASE WHEN category = '금현물' THEN 'ka50081' ELSE 'ka20006' END,
                   '/api/dostk/chart', 0, 0, 'WAITING',
                   '키움 provider mapping이 아직 설정되지 않은 지표입니다.',
                   CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM market_indexes
            WHERE provider = 'KIWOOM_REST'
              AND index_code NOT IN ('KOSPI', 'KOSDAQ')
            """
        )
        conn.exec_driver_sql(
            """
            UPDATE market_index_provider_mappings
            SET is_enabled = 0, is_verified = 0,
                last_test_status = CASE WHEN last_test_status IS NULL OR last_test_status = '' THEN 'WAITING' ELSE last_test_status END,
                last_test_message = CASE
                    WHEN last_test_message IS NULL OR TRIM(last_test_message) = '' THEN '키움 provider mapping이 아직 설정되지 않은 지표입니다.'
                    ELSE last_test_message
                END,
                updated_at = CURRENT_TIMESTAMP
            WHERE provider = 'KIWOOM_REST'
              AND index_code NOT IN ('KOSPI', 'KOSDAQ')
              AND is_verified = 0
            """
        )

        conn.exec_driver_sql(
            """
            UPDATE market_indexes
            SET collection_status = CASE
                    WHEN last_collected_date IS NULL THEN 'WAITING'
                    ELSE collection_status
                END,
                error_message = CASE
                    WHEN error_message IS NULL OR TRIM(error_message) = '' THEN '키움 provider mapping이 아직 설정되지 않은 지표입니다.'
                    ELSE error_message
                END,
                updated_at = CURRENT_TIMESTAMP
            WHERE provider = 'KIWOOM_REST'
              AND provider_symbol IS NULL
              AND index_code NOT IN ('KOSPI', 'KOSDAQ')
            """
        )

        sector_policy_rows = (
            ('KOSPI_MACHINERY', '코스피 기계/장비', '코스피 기계/장비. 키움 ka10101 기계/장비 업종지수 기반', '012', '0', '{"inds_cd":"012"}'),
            ('KOSPI_CONSTRUCTION', '코스피 건설', '코스피 건설. 키움 ka10101 건설 업종지수 기반', '018', '0', '{"inds_cd":"018"}'),
            ('KOSPI_TRANSPORT_WAREHOUSE', '코스피 운송/창고', '코스피 운송/창고. 키움 ka10101 운송/창고 업종지수 기반', '019', '0', '{"inds_cd":"019"}'),
            ('KOSPI_SERVICE', '코스피 일반서비스', '코스피 일반서비스. 키움 ka10101 일반서비스 업종지수 기반', '026', '0', '{"inds_cd":"026"}'),
            ('KOSPI_STEEL_METAL', '코스피 금속', '코스피 금속. 키움 ka10101 금속 업종지수 기반', '011', '0', '{"inds_cd":"011"}'),
            ('KOSDAQ_GENERAL_ELECTRONICS', '코스닥 전기/전자', '코스닥 전기/전자. 키움 ka10101 전기/전자 업종지수 기반', '124', '1', '{"inds_cd":"124"}'),
            ('KOSDAQ_MACHINE_EQUIPMENT', '코스닥 기계/장비', '코스닥 기계/장비. 키움 ka10101 기계/장비 업종지수 기반', '123', '1', '{"inds_cd":"123"}'),
            ('KOSDAQ_CHEMICAL', '코스닥 화학', '코스닥 화학. 키움 ka10101 화학 업종지수 기반', '119', '1', '{"inds_cd":"119"}'),
            ('KOSDAQ_MEDICAL_PRECISION', '코스닥 의료/정밀기기', '코스닥 의료/정밀기기. 키움 ka10101 의료/정밀기기 업종지수 기반', '125', '1', '{"inds_cd":"125"}'),
        )
        for index_code, index_name, description, provider_symbol, market_type, request_params_json in sector_policy_rows:
            conn.exec_driver_sql(
                """
                UPDATE market_indexes
                SET index_name = ?, description = ?, is_active = 1,
                    collection_status = CASE WHEN collection_status IN ('CUSTOM_INDEX_REQUIRED', 'NO_OFFICIAL_INDEX', 'EXCLUDED') THEN 'NOT_COLLECTED' ELSE collection_status END,
                    error_message = CASE WHEN collection_status IN ('CUSTOM_INDEX_REQUIRED', 'NO_OFFICIAL_INDEX', 'EXCLUDED') THEN NULL ELSE error_message END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE index_code = ?
                """,
                (index_name, description, index_code),
            )
            conn.exec_driver_sql(
                """
                INSERT INTO market_index_provider_mappings (
                    index_code, provider, api_type, provider_symbol, market_type, indicator_type, request_params_json,
                    api_id, endpoint_url, is_enabled, is_verified, last_test_status, last_test_message, created_at, updated_at
                )
                VALUES (?, 'KIWOOM_REST', 'SECTOR_DAILY', ?, ?, '????', ?, 'ka20006', '/api/dostk/chart', 0, 0, 'WAITING', 'provider mapping ??? ?????.', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(index_code, provider) DO UPDATE SET
                    api_type = excluded.api_type,
                    provider_symbol = excluded.provider_symbol,
                    market_type = excluded.market_type,
                    indicator_type = excluded.indicator_type,
                    request_params_json = excluded.request_params_json,
                    api_id = excluded.api_id,
                    endpoint_url = excluded.endpoint_url,
                    is_enabled = CASE WHEN market_index_provider_mappings.is_verified = 1 THEN market_index_provider_mappings.is_enabled ELSE 0 END,
                    is_verified = market_index_provider_mappings.is_verified,
                    last_test_status = CASE WHEN market_index_provider_mappings.is_verified = 1 THEN market_index_provider_mappings.last_test_status ELSE 'WAITING' END,
                    last_test_message = CASE WHEN market_index_provider_mappings.is_verified = 1 THEN market_index_provider_mappings.last_test_message ELSE 'provider mapping ??? ?????.' END,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (index_code, provider_symbol, market_type, request_params_json),
            )

        custom_index_rows = (
            ('KOSDAQ_SEMICONDUCTOR', '키움 ka10101 코스닥 업종코드에 공식 반도체 업종지수가 없어 공식 업종지수 수집 대상에서 제외했습니다. DrCT 자체 반도체 테마지수 후보입니다.'),
            ('KOSDAQ_IT_HW', '키움 ka10101 코스닥 업종코드에 공식 IT H/W 업종지수가 없어 공식 업종지수 수집 대상에서 제외했습니다. DrCT 자체 IT H/W 테마지수 후보입니다.'),
        )
        for index_code, reason in custom_index_rows:
            conn.exec_driver_sql(
                """
                UPDATE market_indexes
                SET is_active = 0, collection_status = 'CUSTOM_INDEX_REQUIRED', description = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP
                WHERE index_code = ?
                """,
                (reason, reason, index_code),
            )
            conn.exec_driver_sql(
                """
                UPDATE market_index_provider_mappings
                SET is_enabled = 0, is_verified = 0, provider_symbol = NULL, api_id = NULL, endpoint_url = NULL,
                    last_test_status = 'CUSTOM_INDEX_REQUIRED', last_test_message = ?, updated_at = CURRENT_TIMESTAMP
                WHERE index_code = ? AND provider = 'KIWOOM_REST'
                """,
                (reason, index_code),
            )

        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_indicators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                indicator_code TEXT UNIQUE NOT NULL,
                indicator_name TEXT NOT NULL,
                category TEXT NOT NULL,
                subcategory TEXT,
                data_frequency TEXT NOT NULL,
                chart_type TEXT NOT NULL,
                unit TEXT,
                unit_label TEXT,
                value_label TEXT,
                base_line_value REAL,
                display_order INTEGER DEFAULT 0,
                priority_rank INTEGER DEFAULT 0,
                description TEXT,
                interpretation_note TEXT,
                higher_value_meaning TEXT,
                lower_value_meaning TEXT,
                is_active INTEGER DEFAULT 1,
                collection_status TEXT DEFAULT 'WAITING',
                latest_value REAL,
                latest_value_date TEXT,
                latest_change_value REAL,
                latest_change_pct REAL,
                latest_yoy_pct REAL,
                latest_mom_pct REAL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_indicators_category_order "
            "ON market_indicators(category, is_active, display_order)"
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_indicator_values (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                indicator_code TEXT NOT NULL,
                value_date TEXT NOT NULL,
                period_label TEXT,
                value REAL,
                open_value REAL,
                high_value REAL,
                low_value REAL,
                close_value REAL,
                change_value REAL,
                change_pct REAL,
                mom_pct REAL,
                yoy_pct REAL,
                normalized_value REAL,
                source_provider TEXT,
                source_unit TEXT,
                is_preliminary INTEGER DEFAULT 0,
                release_date TEXT,
                raw_payload_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(indicator_code, value_date),
                FOREIGN KEY (indicator_code) REFERENCES market_indicators(indicator_code) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_indicator_values_code_date "
            "ON market_indicator_values(indicator_code, value_date)"
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_indicator_provider_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                indicator_code TEXT NOT NULL,
                provider TEXT NOT NULL,
                api_type TEXT,
                api_id TEXT,
                endpoint_url TEXT,
                provider_symbol TEXT,
                request_params_json TEXT,
                is_enabled INTEGER DEFAULT 0,
                is_verified INTEGER DEFAULT 0,
                verified_at TEXT,
                last_test_status TEXT,
                last_test_message TEXT,
                last_tested_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(indicator_code, provider),
                FOREIGN KEY (indicator_code) REFERENCES market_indicators(indicator_code) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_indicator_provider_mappings_indicator "
            "ON market_indicator_provider_mappings(indicator_code, provider)"
        )

        market_indicator_rows = (
            ('USD_KRW', '\ub2ec\ub7ec/\uc6d0 \ud658\uc728', 'FX', 'USD', 'DAILY', 'LINE', 'KRW', '\uc6d0', '\ud658\uc728', None, 10, 1, '\uc6d0/\ub2ec\ub7ec \ud658\uc728. 59-B\uc5d0\uc11c BOK ECOS \ub610\ub294 \uacf5\uacf5\ub370\uc774\ud130 provider \uc5f0\uacb0 \uc608\uc815', None, '\uc6d0\ud654 \uc57d\uc138, \uc678\uad6d\uc778 \uc218\uae09 \ubd80\ub2f4 \uac00\ub2a5', '\uc6d0\ud654 \uac15\uc138, \uc704\ud5d8\uc790\uc0b0 \uc120\ud638 \uc644\ud654 \uac00\ub2a5', 1, 'WAITING'),
            ('JPY_KRW', '\uc5d4/\uc6d0 \ud658\uc728', 'FX', 'JPY', 'DAILY', 'LINE', 'KRW', '\uc6d0', '\ud658\uc728', None, 11, 2, '\uc5d4/\uc6d0 \ud658\uc728. 59-B\uc5d0\uc11c BOK ECOS \ub610\ub294 \uacf5\uacf5\ub370\uc774\ud130 provider \uc5f0\uacb0 \uc608\uc815', None, None, None, 1, 'WAITING'),
            ('CNY_KRW', '\uc704\uc548/\uc6d0 \ud658\uc728', 'FX', 'CNY', 'DAILY', 'LINE', 'KRW', '\uc6d0', '\ud658\uc728', None, 12, 3, '\uc704\uc548/\uc6d0 \ud658\uc728. 59-B\uc5d0\uc11c BOK ECOS \ub610\ub294 \uacf5\uacf5\ub370\uc774\ud130 provider \uc5f0\uacb0 \uc608\uc815', None, None, None, 1, 'WAITING'),
            ('BASE_RATE', '\uae30\uc900\uae08\ub9ac', 'RATE', 'POLICY_RATE', 'DAILY', 'LINE', 'PCT', '%', '\uae08\ub9ac', None, 20, 1, '\ud55c\uad6d\uc740\ud589 \uae30\uc900\uae08\ub9ac. ECOS provider \uc6b0\uc120 \ud6c4\ubcf4', None, '\ud560\uc778\uc728 \uc0c1\uc2b9, \uc131\uc7a5\uc8fc \ubd80\ub2f4 \uac00\ub2a5', '\uc720\ub3d9\uc131 \uc644\ud654, \uc131\uc7a5\uc8fc \ubd80\ub2f4 \uc644\ud654 \uac00\ub2a5', 1, 'WAITING'),
            ('CALL_RATE', '\ucf5c\uae08\ub9ac', 'RATE', 'MARKET_RATE', 'DAILY', 'LINE', 'PCT', '%', '\uae08\ub9ac', None, 21, 2, '\ucf5c\uae08\ub9ac. ECOS provider \uc6b0\uc120 \ud6c4\ubcf4', None, None, None, 1, 'WAITING'),
            ('KTB_3Y', '\uad6d\uace0\ucc44 3\ub144', 'RATE', 'BOND_YIELD', 'DAILY', 'LINE', 'PCT', '%', '\uae08\ub9ac', None, 22, 3, '\uad6d\uace0\ucc44 3\ub144 \uae08\ub9ac. ECOS provider \uc6b0\uc120 \ud6c4\ubcf4', None, None, None, 1, 'WAITING'),
            ('KTB_10Y', '\uad6d\uace0\ucc44 10\ub144', 'RATE', 'BOND_YIELD', 'DAILY', 'LINE', 'PCT', '%', '\uae08\ub9ac', None, 23, 4, '\uad6d\uace0\ucc44 10\ub144 \uae08\ub9ac. ECOS provider \uc6b0\uc120 \ud6c4\ubcf4', None, '\uc7a5\uae30 \ud560\uc778\uc728 \uc0c1\uc2b9, \uc131\uc7a5\uc8fc\uc640 2\ucc28\uc804\uc9c0 \ubd80\ub2f4 \uac00\ub2a5', '\uc131\uc7a5\uc8fc \ubd80\ub2f4 \uc644\ud654 \uac00\ub2a5', 1, 'WAITING'),
            ('CPI', '\uc18c\ube44\uc790\ubb3c\uac00\uc9c0\uc218', 'INFLATION', 'CPI', 'MONTHLY', 'BAR_LINE', 'INDEX', '\uc9c0\uc218', '\ubc1c\ud45c\uac12', None, 30, 1, '\uc18c\ube44\uc790\ubb3c\uac00\uc9c0\uc218. KOSIS \ub610\ub294 ECOS provider \ud6c4\ubcf4', None, '\ubb3c\uac00 \uc555\ub825 \uc0c1\uc2b9, \uae08\ub9ac \ubd80\ub2f4 \uac00\ub2a5', '\ubb3c\uac00 \uc555\ub825 \uc644\ud654 \uac00\ub2a5', 1, 'WAITING'),
            ('PPI', '\uc0dd\uc0b0\uc790\ubb3c\uac00\uc9c0\uc218', 'INFLATION', 'PPI', 'MONTHLY', 'BAR_LINE', 'INDEX', '\uc9c0\uc218', '\ubc1c\ud45c\uac12', None, 31, 2, '\uc0dd\uc0b0\uc790\ubb3c\uac00\uc9c0\uc218. KOSIS \ub610\ub294 ECOS provider \ud6c4\ubcf4', None, None, None, 1, 'WAITING'),
            ('CSI', '\uc18c\ube44\uc790\uc2ec\ub9ac\uc9c0\uc218', 'ECONOMY', 'SENTIMENT', 'MONTHLY', 'LINE_WITH_BASELINE', 'INDEX', '\uc9c0\uc218', '\uc9c0\uc218', 100, 40, 1, '\uc18c\ube44\uc790\uc2ec\ub9ac\uc9c0\uc218. ECOS provider \uc6b0\uc120 \ud6c4\ubcf4', None, '\uc18c\ube44\uc2ec\ub9ac \uac1c\uc120, \uc704\ud5d8\uc120\ud638 \uac1c\uc120 \uac00\ub2a5', '\uc18c\ube44\uc2ec\ub9ac \uc704\ucd95 \uac00\ub2a5', 1, 'WAITING'),
            ('BSI_MANUFACTURING', '\uc81c\uc870\uc5c5 BSI', 'ECONOMY', 'BSI', 'MONTHLY', 'LINE_WITH_BASELINE', 'INDEX', '\uc9c0\uc218', '\uc9c0\uc218', 100, 41, 2, '\uc81c\uc870\uc5c5 \uc5c5\ud669 BSI. ECOS provider \uc6b0\uc120 \ud6c4\ubcf4', None, None, None, 1, 'WAITING'),
            ('US_NASDAQ', '나스닥 종합지수', 'GLOBAL_INDEX', 'US_INDEX', 'DAILY', 'LINE', 'INDEX', '지수', '지수', None, 70, 1, 'FRED NASDAQCOM 기반 미국 나스닥 종합지수', None, '미국 성장주 위험선호 개선 가능', '미국 성장주 위험선호 약화 가능', 1, 'WAITING'),
            ('US_SP500', 'S&P 500', 'GLOBAL_INDEX', 'US_INDEX', 'DAILY', 'LINE', 'INDEX', '지수', '지수', None, 71, 2, 'FRED SP500 기반 미국 대표 주가지수', None, '미국 대형주 흐름 개선 가능', '미국 대형주 흐름 약화 가능', 1, 'WAITING'),
            ('US_DOW', '다우존스 산업평균', 'GLOBAL_INDEX', 'US_INDEX', 'DAILY', 'LINE', 'INDEX', '지수', '지수', None, 72, 3, 'FRED DJIA 기반 미국 다우존스 산업평균', None, '미국 산업주 흐름 개선 가능', '미국 산업주 흐름 약화 가능', 1, 'WAITING'),
            ('US_SOX', '필라델피아 반도체지수', 'GLOBAL_INDEX', 'US_SEMICONDUCTOR', 'DAILY', 'LINE', 'INDEX', '지수', '지수', None, 73, 4, 'FRED NASDAQSOX 기반 미국 반도체지수', None, '글로벌 반도체 수급 개선 가능', '글로벌 반도체 수급 약화 가능', 1, 'WAITING'),
            ('US_10Y', '미국 국채 10년', 'GLOBAL_RATE', 'US_TREASURY', 'DAILY', 'LINE', 'PCT', '%', '금리', None, 80, 1, 'FRED DGS10 기반 미국 국채 10년 금리', None, '글로벌 장기금리 부담 가능', '글로벌 장기금리 부담 완화 가능', 1, 'WAITING'),
            ('US_2Y', '미국 국채 2년', 'GLOBAL_RATE', 'US_TREASURY', 'DAILY', 'LINE', 'PCT', '%', '금리', None, 81, 2, 'FRED DGS2 기반 미국 국채 2년 금리', None, '미국 단기금리 부담 가능', '미국 단기금리 부담 완화 가능', 1, 'WAITING'),
            ('US_30Y', '미국 국채 30년', 'GLOBAL_RATE', 'US_TREASURY', 'DAILY', 'LINE', 'PCT', '%', '금리', None, 82, 3, '미국 30년 만기 국채의 Constant Maturity Rate. 미국 초장기 금리와 장기 기대 인플레이션, 기간 프리미엄 및 재정 부담 변화를 관찰하는 참고 지표.', None, '미국 초장기금리 부담 가능', '미국 초장기금리 부담 완화 가능', 1, 'WAITING'),
            ('US_FED_FUNDS', '미국 연방기금금리', 'GLOBAL_RATE', 'US_POLICY_RATE', 'DAILY', 'LINE', 'PCT', '%', '금리', None, 83, 4, 'FRED DFF 기반 미국 연방기금금리', None, '정책금리 부담 가능', '정책금리 부담 완화 가능', 1, 'WAITING'),
        )
        for row in market_indicator_rows:
            conn.exec_driver_sql(
                """
                INSERT INTO market_indicators
                (indicator_code, indicator_name, category, subcategory, data_frequency, chart_type, unit, unit_label,
                 value_label, base_line_value, display_order, priority_rank, description, interpretation_note,
                 higher_value_meaning, lower_value_meaning, is_active, collection_status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(indicator_code) DO UPDATE SET
                    indicator_name = excluded.indicator_name,
                    category = excluded.category,
                    subcategory = excluded.subcategory,
                    data_frequency = excluded.data_frequency,
                    chart_type = excluded.chart_type,
                    unit = excluded.unit,
                    unit_label = excluded.unit_label,
                    value_label = excluded.value_label,
                    base_line_value = excluded.base_line_value,
                    display_order = excluded.display_order,
                    priority_rank = excluded.priority_rank,
                    description = excluded.description,
                    interpretation_note = excluded.interpretation_note,
                    higher_value_meaning = excluded.higher_value_meaning,
                    lower_value_meaning = excluded.lower_value_meaning,
                    is_active = excluded.is_active,
                    collection_status = CASE
                        WHEN market_indicators.collection_status IN ('LATEST', 'PARTIAL', 'ERROR') THEN market_indicators.collection_status
                        ELSE excluded.collection_status
                    END,
                    updated_at = CURRENT_TIMESTAMP
                """,
                row,
            )

        indicator_provider_candidates = {
            'USD_KRW': 'BOK_ECOS',
            'JPY_KRW': 'BOK_ECOS',
            'CNY_KRW': 'BOK_ECOS',
            'BASE_RATE': 'BOK_ECOS',
            'CALL_RATE': 'BOK_ECOS',
            'KTB_3Y': 'BOK_ECOS',
            'KTB_10Y': 'BOK_ECOS',
            'CPI': 'BOK_ECOS',
            'PPI': 'BOK_ECOS',
            'CSI': 'BOK_ECOS',
            'BSI_MANUFACTURING': 'BOK_ECOS',
            'US_NASDAQ': 'FRED',
            'US_SP500': 'FRED',
            'US_DOW': 'FRED',
            'US_SOX': 'FRED',
            'US_10Y': 'FRED',
            'US_2Y': 'FRED',
            'US_30Y': 'FRED',
            'US_FED_FUNDS': 'FRED',
        }
        for indicator_code, provider in indicator_provider_candidates.items():
            conn.exec_driver_sql(
                """
                INSERT INTO market_indicator_provider_mappings
                (indicator_code, provider, api_type, api_id, endpoint_url, provider_symbol, request_params_json,
                 is_enabled, is_verified, last_test_status, last_test_message, created_at, updated_at)
                VALUES (?, ?, 'ECONOMIC_STAT', NULL, NULL, NULL, '{}', 0, 0, 'WAITING', 'provider mapping check required', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(indicator_code, provider) DO UPDATE SET
                    api_type = COALESCE(market_indicator_provider_mappings.api_type, excluded.api_type),
                    request_params_json = COALESCE(market_indicator_provider_mappings.request_params_json, excluded.request_params_json),
                    last_test_status = CASE WHEN market_indicator_provider_mappings.is_verified = 1 THEN market_indicator_provider_mappings.last_test_status ELSE 'WAITING' END,
                    last_test_message = CASE WHEN market_indicator_provider_mappings.is_verified = 1 THEN market_indicator_provider_mappings.last_test_message ELSE 'provider mapping check required' END,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (indicator_code, provider),
            )

        ecos_mapping_defaults = {
            'USD_KRW': ('731Y001', 'D', '0000001', '\uc6d0/\ubbf8\uad6d\ub2ec\ub7ec(\ub9e4\ub9e4\uae30\uc900\uc728)', '\uc6d0'),
            'JPY_KRW': ('731Y001', 'D', '0000002', '\uc6d0/\uc77c\ubcf8\uc5d4(100\uc5d4)', '\uc6d0'),
            'CNY_KRW': ('731Y001', 'D', '0000053', '\uc6d0/\uc704\uc548(\ub9e4\ub9e4\uae30\uc900\uc728)', '\uc6d0'),
            'BASE_RATE': ('722Y001', 'D', '0101000', '\ud55c\uad6d\uc740\ud589 \uae30\uc900\uae08\ub9ac', '\uc5f0%'),
            'CALL_RATE': ('817Y002', 'D', '010101000', '\ucf5c\uae08\ub9ac(1\uc77c, \uc804\uccb4\uac70\ub798)', '\uc5f0%'),
            'KTB_3Y': ('817Y002', 'D', '010200000', '\uad6d\uace0\ucc44(3\ub144)', '\uc5f0%'),
            'KTB_10Y': ('817Y002', 'D', '010210000', '\uad6d\uace0\ucc44(10\ub144)', '\uc5f0%'),
        }
        for indicator_code, (stat_code, cycle, item_code, item_name, source_unit) in ecos_mapping_defaults.items():
            request_params_json = json.dumps(
                {
                    'stat_code': stat_code,
                    'cycle': cycle,
                    'item_code1': item_code,
                    'item_name1': item_name,
                    'value_field': 'DATA_VALUE',
                    'scale': 1,
                    'source_unit': source_unit,
                    'date_format': 'ECOS_TIME',
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            conn.exec_driver_sql(
                """
                UPDATE market_indicator_provider_mappings
                SET api_type = CASE WHEN is_verified = 1 THEN api_type ELSE 'STATISTIC_SEARCH' END,
                    api_id = CASE WHEN is_verified = 1 THEN api_id ELSE 'ECOS_STATISTIC_SEARCH' END,
                    endpoint_url = CASE WHEN is_verified = 1 THEN endpoint_url ELSE '/api/StatisticSearch' END,
                    provider_symbol = CASE WHEN is_verified = 1 THEN provider_symbol ELSE ? END,
                    request_params_json = CASE WHEN is_verified = 1 THEN request_params_json ELSE ? END,
                    last_test_status = CASE WHEN is_verified = 1 THEN last_test_status ELSE 'WAITING' END,
                    last_test_message = CASE WHEN is_verified = 1 THEN last_test_message ELSE 'ECOS mapping candidate ready; test required' END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE indicator_code = ? AND provider = 'BOK_ECOS'
                """,
                (f'{stat_code}:{item_code}', request_params_json, indicator_code),
            )


        fred_mapping_defaults = {
            'US_NASDAQ': ('NASDAQCOM', 'INDEX'),
            'US_SP500': ('SP500', 'INDEX'),
            'US_DOW': ('DJIA', 'INDEX'),
            'US_SOX': ('NASDAQSOX', 'INDEX'),
            'US_10Y': ('DGS10', 'PCT'),
            'US_2Y': ('DGS2', 'PCT'),
            'US_30Y': ('DGS30', 'PCT'),
            'US_FED_FUNDS': ('DFF', 'PCT'),
        }
        for indicator_code, (series_id, source_unit) in fred_mapping_defaults.items():
            request_params_json = json.dumps(
                {
                    'series_id': series_id,
                    'frequency': 'd',
                    'value_field': 'value',
                    'date_field': 'date',
                    'scale': 1,
                    'source_unit': source_unit,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            conn.exec_driver_sql(
                """
                UPDATE market_indicator_provider_mappings
                SET api_type = CASE WHEN is_verified = 1 THEN api_type ELSE 'SERIES_OBSERVATIONS' END,
                    api_id = CASE WHEN is_verified = 1 THEN api_id ELSE 'FRED_SERIES_OBSERVATIONS' END,
                    endpoint_url = CASE WHEN is_verified = 1 THEN endpoint_url ELSE '/fred/series/observations' END,
                    provider_symbol = CASE WHEN is_verified = 1 THEN provider_symbol ELSE ? END,
                    request_params_json = CASE WHEN is_verified = 1 THEN request_params_json ELSE ? END,
                    last_test_status = CASE WHEN is_verified = 1 THEN last_test_status ELSE 'WAITING' END,
                    last_test_message = CASE WHEN is_verified = 1 THEN last_test_message ELSE 'FRED series candidate ready; test required' END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE indicator_code = ? AND provider = 'FRED'
                """,
                (series_id, request_params_json, indicator_code),
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
                theme_id INTEGER,
                stock_id INTEGER NOT NULL,
                mapping_source TEXT NOT NULL DEFAULT 'manual',
                confidence_score REAL,
                is_primary INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                stock_memo TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(theme_id, stock_id),
                FOREIGN KEY (theme_id) REFERENCES market_themes(id) ON DELETE CASCADE,
                FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
            )
            """
        )
        market_theme_stock_columns = {
            str(row[1]) for row in conn.exec_driver_sql("PRAGMA table_info(market_theme_stocks)").fetchall()
        }
        if "stock_memo" not in market_theme_stock_columns:
            conn.exec_driver_sql("ALTER TABLE market_theme_stocks ADD COLUMN stock_memo TEXT")
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
                FOREIGN KEY (theme_id) REFERENCES market_themes(id) ON DELETE SET NULL
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
            """
            CREATE TABLE IF NOT EXISTS market_theme_realtime_returns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_date TEXT NOT NULL,
                theme_id INTEGER NOT NULL,
                stock_id INTEGER NOT NULL,
                change_rate REAL NOT NULL,
                trading_value INTEGER,
                collected_at TEXT NOT NULL,
                UNIQUE(trade_date, theme_id, stock_id),
                FOREIGN KEY (theme_id) REFERENCES market_themes(id) ON DELETE CASCADE,
                FOREIGN KEY (stock_id) REFERENCES stocks(id) ON DELETE CASCADE
            )
            """
        )
        _ensure_column(conn, "market_theme_realtime_returns", "trading_value", "INTEGER")
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_theme_realtime_theme_date ON market_theme_realtime_returns(theme_id, trade_date)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_theme_realtime_stock_date ON market_theme_realtime_returns(stock_id, trade_date)"
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_theme_return_prediction_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_date TEXT NOT NULL,
                data_cutoff_date TEXT NOT NULL,
                data_cutoff_at TEXT,
                prediction_stage TEXT NOT NULL DEFAULT 'PREMARKET',
                prediction_horizon TEXT NOT NULL DEFAULT 'NEXT_SELECTED_DATE',
                official_method TEXT NOT NULL DEFAULT 'RULE',
                status TEXT NOT NULL DEFAULT 'DRAFT',
                revision_count INTEGER NOT NULL DEFAULT 1,
                rule_version TEXT NOT NULL,
                model_version TEXT,
                first_predicted_at TEXT NOT NULL,
                last_predicted_at TEXT NOT NULL,
                evaluated_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(target_date, prediction_stage, prediction_horizon)
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_theme_return_prediction_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                theme_id INTEGER NOT NULL,
                prediction_method TEXT NOT NULL DEFAULT 'RULE',
                is_official INTEGER NOT NULL DEFAULT 1,
                model_version TEXT,
                base_change_rate REAL,
                predicted_change_rate REAL,
                prediction_score REAL,
                predicted_rank INTEGER,
                price_score REAL,
                flow_score REAL,
                breadth_score REAL,
                alignment_score REAL,
                liquidity_score REAL,
                market_environment_score REAL,
                penalty_score REAL NOT NULL DEFAULT 0,
                data_coverage_rate REAL NOT NULL DEFAULT 0,
                actual_change_rate REAL,
                actual_rank INTEGER,
                signed_gap REAL,
                absolute_gap REAL,
                rank_gap INTEGER,
                direction_hit INTEGER,
                baseline_absolute_error REAL,
                prediction_effect REAL,
                evaluation_status TEXT NOT NULL DEFAULT 'NOT_EVALUATED',
                evaluated_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(run_id, theme_id, prediction_method),
                FOREIGN KEY (run_id) REFERENCES market_theme_return_prediction_runs(id) ON DELETE CASCADE,
                FOREIGN KEY (theme_id) REFERENCES market_themes(id) ON DELETE CASCADE
            )
            """
        )
        _ensure_column(conn, "market_theme_return_prediction_items", "model_version", "TEXT")
        _ensure_column(conn, "market_theme_return_prediction_items", "top5_probability", "REAL")
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_theme_return_prediction_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL UNIQUE,
                theme_count INTEGER NOT NULL,
                evaluable_theme_count INTEGER NOT NULL,
                return_mae REAL,
                return_rmse REAL,
                mean_signed_gap REAL,
                mean_rank_error REAL,
                top1_hit REAL,
                precision_at_3 REAL,
                precision_at_5 REAL,
                precision_at_10 REAL,
                direction_accuracy REAL,
                spearman_rank_correlation REAL,
                ndcg_at_5 REAL,
                baseline_mae REAL,
                mae_improvement REAL,
                baseline_precision_at_5 REAL,
                improved_theme_count INTEGER NOT NULL DEFAULT 0,
                evaluation_status TEXT NOT NULL,
                evaluated_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES market_theme_return_prediction_runs(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_theme_return_prediction_rule_sets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_version TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_theme_return_prediction_rule_parameters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_set_id INTEGER NOT NULL,
                parameter_code TEXT NOT NULL,
                parameter_value REAL NOT NULL,
                description TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(rule_set_id, parameter_code),
                FOREIGN KEY (rule_set_id) REFERENCES market_theme_return_prediction_rule_sets(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_theme_prediction_runs_cutoff ON market_theme_return_prediction_runs(data_cutoff_date, status)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_theme_prediction_items_run_rank ON market_theme_return_prediction_items(run_id, predicted_rank)")
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_theme_return_prediction_models (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_version TEXT NOT NULL UNIQUE,
                model_type TEXT NOT NULL,
                feature_version TEXT NOT NULL,
                status TEXT NOT NULL,
                trained_at TEXT NOT NULL,
                train_start_date TEXT NOT NULL,
                train_end_date TEXT NOT NULL,
                distinct_train_dates INTEGER NOT NULL,
                train_row_count INTEGER NOT NULL,
                validation_fold_count INTEGER NOT NULL,
                validation_mae REAL,
                validation_rmse REAL,
                validation_mean_signed_gap REAL,
                validation_direction_accuracy REAL,
                validation_precision_at_3 REAL,
                validation_precision_at_5 REAL,
                validation_precision_at_10 REAL,
                validation_spearman REAL,
                validation_ndcg_at_5 REAL,
                validation_mean_rank_error REAL,
                rule_validation_mae REAL,
                rule_validation_precision_at_5 REAL,
                rule_validation_ndcg_at_5 REAL,
                baseline_validation_mae REAL,
                baseline_validation_precision_at_5 REAL,
                baseline_validation_ndcg_at_5 REAL,
                artifact_path TEXT NOT NULL,
                sklearn_version TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_theme_return_prediction_method_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                prediction_method TEXT NOT NULL,
                model_version TEXT NOT NULL DEFAULT '',
                theme_count INTEGER NOT NULL,
                evaluable_theme_count INTEGER NOT NULL,
                return_mae REAL,
                return_rmse REAL,
                mean_signed_gap REAL,
                mean_rank_error REAL,
                top1_hit REAL,
                precision_at_3 REAL,
                precision_at_5 REAL,
                precision_at_10 REAL,
                direction_accuracy REAL,
                spearman_rank_correlation REAL,
                ndcg_at_5 REAL,
                evaluated_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(run_id, prediction_method, model_version),
                FOREIGN KEY (run_id) REFERENCES market_theme_return_prediction_runs(id) ON DELETE CASCADE
            )
            """
        )
        _ensure_column(conn, "market_theme_return_prediction_models", "target_type", "TEXT NOT NULL DEFAULT 'RAW_RETURN'")
        _ensure_column(conn, "market_theme_return_prediction_models", "parent_model_version", "TEXT")
        _ensure_column(conn, "market_theme_return_prediction_models", "selection_gate_status", "TEXT NOT NULL DEFAULT 'NOT_EVALUATED'")
        _ensure_column(conn, "market_theme_return_prediction_models", "selection_reason", "TEXT")
        _ensure_column(conn, "market_theme_return_prediction_models", "shadow_selected_at", "TEXT")
        _ensure_column(conn, "market_theme_return_prediction_models", "validation_improving_fold_count", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "market_theme_return_prediction_models", "metric_version", "TEXT NOT NULL DEFAULT 'THEME_RETURN_METRIC_V1'")
        _ensure_column(conn, "market_theme_return_prediction_models", "validation_precision_top20", "REAL")
        _ensure_column(conn, "market_theme_return_prediction_models", "validation_recall_top20", "REAL")
        _ensure_column(conn, "market_theme_return_prediction_models", "validation_f1_top20", "REAL")
        _ensure_column(conn, "market_theme_return_prediction_models", "validation_brier", "REAL")
        _ensure_column(conn, "market_theme_return_prediction_models", "validation_log_loss", "REAL")
        _ensure_column(conn, "market_theme_return_prediction_models", "validation_calibration_error", "REAL")
        _ensure_column(conn, "market_theme_return_prediction_models", "raw_validation_brier", "REAL")
        _ensure_column(conn, "market_theme_return_prediction_models", "raw_validation_log_loss", "REAL")
        _ensure_column(conn, "market_theme_return_prediction_models", "raw_validation_calibration_error", "REAL")
        _ensure_column(conn, "market_theme_return_prediction_models", "calibration_status", "TEXT NOT NULL DEFAULT 'NOT_EVALUATED'")
        _ensure_column(conn, "market_theme_return_prediction_models", "probability_display_mode", "TEXT NOT NULL DEFAULT 'SCORE'")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_theme_prediction_models_status ON market_theme_return_prediction_models(status, trained_at)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_theme_prediction_models_gate ON market_theme_return_prediction_models(selection_gate_status, validation_ndcg_at_5 DESC)")
        _ensure_column(conn, "market_theme_return_prediction_method_metrics", "metric_version", "TEXT NOT NULL DEFAULT 'THEME_RETURN_METRIC_V1'")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_theme_prediction_method_metrics_run ON market_theme_return_prediction_method_metrics(run_id, prediction_method)")
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_theme_observation_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, target_date TEXT NOT NULL UNIQUE,
                data_cutoff_date TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'DRAFT', method TEXT NOT NULL,
                model_version TEXT, feature_version TEXT NOT NULL, display_mode TEXT NOT NULL,
                calculated_at TEXT NOT NULL, evaluated_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_theme_observation_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER NOT NULL, theme_id INTEGER NOT NULL,
                observation_rank INTEGER, relative_strength_probability REAL, relative_strength_score REAL,
                top20_probability REAL, status_code TEXT NOT NULL, confidence_level TEXT NOT NULL,
                data_coverage_rate REAL NOT NULL DEFAULT 0, base_change_rate REAL, price_score REAL,
                flow_score REAL, breadth_score REAL, liquidity_score REAL, technical_score REAL,
                market_environment_score REAL, penalty_score REAL NOT NULL DEFAULT 0, actual_change_rate REAL,
                actual_rank INTEGER, actual_top20 INTEGER, rank_gap INTEGER, probability_error REAL,
                evaluation_status TEXT NOT NULL DEFAULT 'PENDING', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                UNIQUE(run_id,theme_id), FOREIGN KEY(run_id) REFERENCES market_theme_observation_runs(id) ON DELETE CASCADE,
                FOREIGN KEY(theme_id) REFERENCES market_themes(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_theme_observation_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER NOT NULL UNIQUE, theme_count INTEGER NOT NULL,
                evaluable_theme_count INTEGER NOT NULL, precision_top20 REAL, recall_top20 REAL, f1_top20 REAL,
                precision_at_5 REAL, ndcg_at_5 REAL, spearman_rank_correlation REAL, mean_rank_error REAL,
                brier_score REAL, log_loss REAL, calibration_error REAL, evaluation_status TEXT NOT NULL,
                evaluated_at TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES market_theme_observation_runs(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_theme_observation_runs_cutoff ON market_theme_observation_runs(data_cutoff_date,status)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_theme_observation_items_rank ON market_theme_observation_items(run_id,observation_rank)")
        _ensure_column(conn, "market_theme_observation_runs", "calculation_mode", "TEXT NOT NULL DEFAULT 'CURRENT_MARKET_DATA'")
        _ensure_column(conn, "market_theme_observation_runs", "market_refresh_requested", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "market_theme_observation_runs", "market_refresh_status", "TEXT NOT NULL DEFAULT 'NOT_REQUESTED'")
        _ensure_column(conn, "market_theme_observation_runs", "market_indicator_refreshed_at", "TEXT")
        _ensure_column(conn, "market_theme_observation_runs", "market_indicator_data_asof_at", "TEXT")
        _ensure_column(conn, "market_theme_observation_runs", "market_indicator_updated_count", "INTEGER")
        _ensure_column(conn, "market_theme_observation_runs", "market_indicator_failed_count", "INTEGER")
        _ensure_column(conn, "market_theme_observation_runs", "market_collection_run_id", "INTEGER")
        _ensure_column(conn, "market_theme_observation_runs", "revision_count", "INTEGER NOT NULL DEFAULT 0")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_theme_observation_runs_mode ON market_theme_observation_runs(calculation_mode,status)")
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_theme_observation_validation_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT, target_date TEXT NOT NULL, theme_id INTEGER NOT NULL,
                calculation_mode TEXT NOT NULL, observation_rule_version TEXT NOT NULL,
                model_version TEXT NOT NULL DEFAULT '', metric_version TEXT NOT NULL,
                observation_score REAL, observation_rank INTEGER NOT NULL, status_code TEXT,
                data_coverage_rate REAL, actual_rank INTEGER, actual_top20 INTEGER, rank_error INTEGER,
                rank_gap INTEGER, top20_hit INTEGER, refresh_score_delta REAL,
                refresh_rank_improvement INTEGER, refresh_effect INTEGER,
                evaluation_status TEXT NOT NULL DEFAULT 'PENDING', evaluated_at TEXT,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                UNIQUE(target_date,theme_id,calculation_mode,observation_rule_version,model_version),
                FOREIGN KEY(theme_id) REFERENCES market_themes(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_theme_observation_validation_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT, target_date TEXT NOT NULL, calculation_mode TEXT NOT NULL,
                observation_rule_version TEXT NOT NULL, model_version TEXT NOT NULL DEFAULT '', metric_version TEXT NOT NULL,
                total_theme_count INTEGER NOT NULL, evaluable_theme_count INTEGER NOT NULL,
                evaluation_coverage_rate REAL NOT NULL, precision_top20 REAL, recall_top20 REAL, f1_top20 REAL,
                precision_at_5 REAL, ndcg_at_5 REAL, spearman REAL, mean_rank_error REAL,
                top5_actual_top20_count INTEGER NOT NULL DEFAULT 0, improved_theme_count INTEGER,
                worsened_theme_count INTEGER, unchanged_theme_count INTEGER, mean_rank_error_current REAL,
                mean_rank_error_refreshed REAL, mean_refresh_effect REAL, current_precision_top20 REAL,
                refreshed_precision_top20 REAL, current_ndcg_at_5 REAL, refreshed_ndcg_at_5 REAL,
                evaluation_status TEXT NOT NULL, evaluated_at TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                UNIQUE(target_date,calculation_mode,observation_rule_version,model_version)
            )
            """
        )
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_theme_observation_validation_samples_date ON market_theme_observation_validation_samples(target_date)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_theme_observation_validation_samples_theme_date ON market_theme_observation_validation_samples(theme_id,target_date)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_theme_observation_validation_samples_date_mode ON market_theme_observation_validation_samples(target_date,calculation_mode)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_theme_observation_validation_metrics_date ON market_theme_observation_validation_metrics(target_date)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_theme_observation_validation_metrics_mode_date ON market_theme_observation_validation_metrics(calculation_mode,target_date)")
        conn.exec_driver_sql(
            """
            INSERT OR IGNORE INTO market_theme_return_prediction_rule_sets
            (rule_version, name, status, is_active, created_at, updated_at)
            VALUES ('RULE_V1', '규칙 기반 테마등락예측 V1', 'ACTIVE', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        )
        prediction_rule_set_id = conn.exec_driver_sql(
            "SELECT id FROM market_theme_return_prediction_rule_sets WHERE rule_version='RULE_V1'"
        ).scalar()
        prediction_parameters = [
            ("PRICE_WEIGHT", 0.25, "가격 모멘텀 가중치"),
            ("FLOW_WEIGHT", 0.25, "수급 강도 가중치"),
            ("BREADTH_WEIGHT", 0.15, "연결 종목 확산도 가중치"),
            ("ALIGNMENT_WEIGHT", 0.15, "가격·수급 결합 가중치"),
            ("LIQUIDITY_WEIGHT", 0.10, "거래대금 가중치"),
            ("MARKET_ENVIRONMENT_WEIGHT", 0.10, "시장환경 가중치"),
            ("OVERHEAT_PENALTY_MAX", 15.0, "최근 급등 과열 최대 감점"),
            ("CONCENTRATION_PENALTY_MAX", 10.0, "단일 종목 집중 최대 감점"),
            ("LOW_COVERAGE_PENALTY_MAX", 20.0, "낮은 수집률 최대 감점"),
            ("FLOW_DIVERGENCE_PENALTY_MAX", 10.0, "가격·수급 이탈 최대 감점"),
            ("MIN_DATA_COVERAGE", 0.70, "공식 순위 최소 데이터 수집률"),
            ("PREDICTION_SCALE", 1.0, "예상 등락률 변동성 배율"),
            ("PREDICTION_BIAS", 0.0, "예상 등락률 편향 보정"),
            ("PREDICTION_MIN", -20.0, "예상 등락률 하한"),
            ("PREDICTION_MAX", 20.0, "예상 등락률 상한"),
            ("DIRECTION_NEUTRAL_BAND", 0.5, "방향 평가 중립 구간"),
        ]
        conn.exec_driver_sql(
            """
            INSERT OR IGNORE INTO market_theme_return_prediction_rule_parameters
            (rule_set_id, parameter_code, parameter_value, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            [(prediction_rule_set_id, code, value, description) for code, value, description in prediction_parameters],
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
                period_type TEXT NOT NULL DEFAULT 'D' CHECK(period_type IN ('D', 'M')),
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                theme_id INTEGER,
                title TEXT NOT NULL,
                summary TEXT,
                news_url TEXT,
                event_type TEXT NOT NULL DEFAULT 'news',
                importance TEXT NOT NULL DEFAULT 'medium',
                memo TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (theme_id) REFERENCES market_themes(id) ON DELETE SET NULL
            )
            """
        )
        _ensure_column(conn, "market_calendar_events", "period_type", "TEXT NOT NULL DEFAULT 'D' CHECK(period_type IN ('D', 'M'))")
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
        stock_tracking_item_columns = {
            str(row[1]) for row in conn.exec_driver_sql("PRAGMA table_info(stock_tracking_items)").fetchall()
        }
        for column_sql in (
            "entry_close_price REAL",
            "entry_close_date TEXT",
            "latest_close_price REAL",
            "latest_close_date TEXT",
            "tracking_return_pct REAL",
            "price_updated_at TEXT",
        ):
            column_name = column_sql.split()[0]
            if column_name not in stock_tracking_item_columns:
                conn.exec_driver_sql(f"ALTER TABLE stock_tracking_items ADD COLUMN {column_sql}")
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
            "CREATE INDEX IF NOT EXISTS idx_market_trend_events_stock_trade_date "
            "ON market_trend_events(stock_id, trade_date, is_active)"
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
        conn.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ux_telegram_sources_channel_username ON telegram_sources(channel_username)")
        telegram_item_columns = {str(row[1]) for row in conn.exec_driver_sql(
            "PRAGMA table_info(telegram_items)"
        ).fetchall()}
        if telegram_item_columns and "message_fingerprint" not in telegram_item_columns:
            conn.exec_driver_sql("""
                CREATE TABLE telegram_items_v2 (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    collection_date TEXT NOT NULL,
                    message_at TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT,
                    source_url TEXT,
                    message_fingerprint TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(collection_date, message_fingerprint)
                )
            """)
            legacy_rows = conn.exec_driver_sql("""
                SELECT id, message_date, item_title, message_text,
                       COALESCE(NULLIF(normalized_url, ''), NULLIF(item_url, '')),
                       COALESCE(NULLIF(created_at, ''), CURRENT_TIMESTAMP)
                FROM telegram_items ORDER BY id
            """).fetchall()
            for row in legacy_rows:
                title = _telegram_migration_title(row[2], row[3])
                source_url = _telegram_canonical_url(row[4])
                fingerprint = _telegram_fingerprint(row[3], source_url, title)
                conn.exec_driver_sql("""
                    INSERT OR IGNORE INTO telegram_items_v2
                    (id, collection_date, message_at, title, summary, source_url, message_fingerprint, created_at)
                    VALUES (?, substr(?, 1, 10), ?, ?, NULL, ?, ?, ?)
                """, (row[0], row[1], row[1], title, source_url, fingerprint, row[5]))
            conn.exec_driver_sql("DROP TABLE telegram_items")
            conn.exec_driver_sql("ALTER TABLE telegram_items_v2 RENAME TO telegram_items")
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS telegram_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                collection_date TEXT NOT NULL,
                message_at TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT,
                source_url TEXT,
                message_fingerprint TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(collection_date, message_fingerprint)
            )
        """)
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS telegram_message_exclusions (
                exclusion_date TEXT NOT NULL,
                message_fingerprint TEXT NOT NULL,
                PRIMARY KEY (exclusion_date, message_fingerprint)
            )
        """)
        conn.exec_driver_sql("DROP TABLE IF EXISTS telegram_daily_summaries")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_telegram_items_collection_date ON telegram_items(collection_date)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_telegram_items_message_at ON telegram_items(message_at)")
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
        if "training_account_id" not in simulation_session_columns:
            conn.exec_driver_sql("ALTER TABLE simulation_sessions ADD COLUMN training_account_id INTEGER")
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
            "CREATE INDEX IF NOT EXISTS idx_simulation_sessions_training_account ON simulation_sessions(training_account_id)"
        )
        session_account_rows = conn.exec_driver_sql(
            """
            SELECT id, options_json
            FROM simulation_sessions
            WHERE training_account_id IS NULL
              AND options_json IS NOT NULL
            """
        ).mappings().fetchall()
        for row in session_account_rows:
            try:
                options = json.loads(str(row["options_json"] or "{}"))
            except json.JSONDecodeError:
                continue
            account_id = options.get("training_account_id")
            if account_id:
                conn.exec_driver_sql(
                    "UPDATE simulation_sessions SET training_account_id = ? WHERE id = ?",
                    (int(account_id), int(row["id"])),
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
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS kms_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id INTEGER,
                name TEXT NOT NULL,
                description TEXT,
                sort_order INTEGER NOT NULL DEFAULT 100,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (parent_id) REFERENCES kms_categories(id) ON DELETE SET NULL
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_kms_categories_parent_name "
            "ON kms_categories(COALESCE(parent_id, -1), name)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_kms_categories_active_sort "
            "ON kms_categories(is_active, sort_order)"
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS kms_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                summary TEXT,
                content TEXT NOT NULL,
                source_url TEXT,
                importance TEXT NOT NULL DEFAULT '보통',
                learning_status TEXT NOT NULL DEFAULT '미정리',
                is_pinned INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (category_id) REFERENCES kms_categories(id) ON DELETE RESTRICT
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_kms_posts_category_active "
            "ON kms_posts(category_id, is_active, updated_at)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_kms_posts_status_importance "
            "ON kms_posts(learning_status, importance)"
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS kms_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                use_count INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_kms_tags_active_count "
            "ON kms_tags(is_active, use_count DESC, name)"
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS kms_post_tags (
                post_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                PRIMARY KEY (post_id, tag_id),
                FOREIGN KEY (post_id) REFERENCES kms_posts(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES kms_tags(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_kms_post_tags_tag_id "
            "ON kms_post_tags(tag_id)"
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS kms_setting_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_code TEXT NOT NULL UNIQUE,
                group_name TEXT NOT NULL,
                description TEXT,
                sort_order INTEGER NOT NULL DEFAULT 100,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS kms_setting_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                item_code TEXT NOT NULL,
                item_name TEXT NOT NULL,
                description TEXT,
                color TEXT,
                icon TEXT,
                sort_order INTEGER NOT NULL DEFAULT 100,
                is_default INTEGER NOT NULL DEFAULT 0,
                is_system INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (group_id) REFERENCES kms_setting_groups(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_kms_setting_items_group_code "
            "ON kms_setting_items(group_id, item_code)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_kms_setting_items_group_sort "
            "ON kms_setting_items(group_id, is_active, sort_order)"
        )
        for column_name, column_sql in {
            "tag_type_id": "INTEGER",
            "color": "TEXT",
            "entity_type": "TEXT",
            "entity_id": "INTEGER",
        }.items():
            _ensure_column(conn, "kms_tags", column_name, column_sql)
        for column_name, column_sql in {
            "one_line_conclusion": "TEXT",
            "legacy_source_type": "TEXT",
            "legacy_source_id": "INTEGER",
            "para_type_id": "INTEGER",
            "knowledge_category_id": "INTEGER",
            "status_id": "INTEGER",
            "importance_id": "INTEGER",
            "usage_context_id": "INTEGER",
            "source_type_id": "INTEGER",
            "source_title": "TEXT",
            "ai_extract_status": "TEXT NOT NULL DEFAULT 'PENDING'",
            "embedding_status": "TEXT NOT NULL DEFAULT 'PENDING'",
        }.items():
            _ensure_column(conn, "kms_posts", column_name, column_sql)
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS kms_knowledge_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                legacy_post_id INTEGER UNIQUE,
                legacy_source_type TEXT,
                legacy_source_id INTEGER,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                content_format TEXT NOT NULL DEFAULT 'HTML',
                one_line_conclusion TEXT,
                summary TEXT,
                para_type_id INTEGER,
                category_id INTEGER,
                status_id INTEGER,
                importance_id INTEGER,
                usage_context_id INTEGER,
                source_type_id INTEGER,
                source_url TEXT,
                source_title TEXT,
                ai_extract_status TEXT NOT NULL DEFAULT 'PENDING',
                embedding_status TEXT NOT NULL DEFAULT 'PENDING',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (legacy_post_id) REFERENCES kms_posts(id) ON DELETE SET NULL
            )
            """
        )
        for column_name, column_sql in {
            "legacy_source_type": "TEXT",
            "legacy_source_id": "INTEGER",
            "content_format": "TEXT NOT NULL DEFAULT 'HTML'",
        }.items():
            _ensure_column(conn, "kms_knowledge_items", column_name, column_sql)
        _drop_column_if_exists(conn, "kms_knowledge_items", "content_html")
        _drop_column_if_exists(conn, "kms_knowledge_items", "content_markdown")
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_kms_knowledge_items_filters "
            "ON kms_knowledge_items(para_type_id, category_id, status_id, importance_id, is_active)"
        )
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_kms_knowledge_items_legacy_source "
            "ON kms_knowledge_items(legacy_source_type, legacy_source_id)"
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS chart_marker_group_knowledge_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                marker_group_id INTEGER NOT NULL,
                knowledge_item_id INTEGER NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(marker_group_id, knowledge_item_id),
                FOREIGN KEY(marker_group_id) REFERENCES chart_marker_groups(id) ON DELETE CASCADE,
                FOREIGN KEY(knowledge_item_id) REFERENCES kms_knowledge_items(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_chart_marker_group_knowledge_sort "
            "ON chart_marker_group_knowledge_links(marker_group_id, sort_order, id)"
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS kms_knowledge_extractions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                knowledge_item_id INTEGER NOT NULL,
                extraction_type TEXT NOT NULL,
                extraction_text TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'USER',
                model_name TEXT,
                confidence_score REAL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (knowledge_item_id) REFERENCES kms_knowledge_items(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS kms_knowledge_item_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                knowledge_item_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                weight REAL NOT NULL DEFAULT 1.0,
                source TEXT NOT NULL DEFAULT 'USER',
                is_confirmed INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                UNIQUE (knowledge_item_id, tag_id),
                FOREIGN KEY (knowledge_item_id) REFERENCES kms_knowledge_items(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES kms_tags(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_kms_knowledge_item_tags_tag_id "
            "ON kms_knowledge_item_tags(tag_id)"
        )
        conn.exec_driver_sql(
            "DELETE FROM kms_knowledge_item_tags "
            "WHERE knowledge_item_id IN (SELECT id FROM kms_knowledge_items WHERE UPPER(COALESCE(content_format, '')) = 'MARKDOWN')"
        )
        conn.exec_driver_sql(
            "DELETE FROM kms_knowledge_extractions "
            "WHERE knowledge_item_id IN (SELECT id FROM kms_knowledge_items WHERE UPPER(COALESCE(content_format, '')) = 'MARKDOWN')"
        )
        conn.exec_driver_sql(
            """
            DELETE FROM kms_knowledge_extractions
            WHERE source = 'AI'
              AND extraction_type NOT IN ('SUMMARY_HELP', 'AI_ERROR')
            """
        )
        conn.exec_driver_sql(
            """
            DELETE FROM kms_knowledge_item_tags
            WHERE source = 'AI'
              AND is_confirmed = 0
            """
        )
        conn.exec_driver_sql("DELETE FROM kms_knowledge_items WHERE UPPER(COALESCE(content_format, '')) = 'MARKDOWN'")
        conn.exec_driver_sql(
            "UPDATE kms_knowledge_items SET content_format = 'HTML' "
            "WHERE content_format IS NULL OR UPPER(content_format) <> 'HTML'"
        )
        _seed_kms_settings(conn)
        for sort_order, category_name in enumerate(
            ["시장", "재료", "수급", "차트", "재무", "기법", "심리", "리스크", "복기", "자료"],
            start=1,
        ):
            conn.exec_driver_sql(
                """
                INSERT OR IGNORE INTO kms_categories
                (parent_id, name, description, sort_order, is_active, created_at, updated_at)
                VALUES (NULL, ?, NULL, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (category_name, sort_order * 10),
            )


def _runtime_table_columns(conn, table_name: str) -> set[str]:
    return {str(row[1]) for row in conn.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()}


def _runtime_add_column_if_missing(conn, table_name: str, column_name: str, column_sql: str) -> None:
    if column_name not in _runtime_table_columns(conn, table_name):
        conn.exec_driver_sql(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")


def ensure_market_data_collection_schema() -> None:
    if not DATABASE_URL.startswith("sqlite"):
        return

    with engine.begin() as conn:
        _runtime_add_column_if_missing(conn, "market_index_daily_prices", "collected_at", "collected_at TEXT")
        _runtime_add_column_if_missing(conn, "market_index_daily_prices", "revised_at", "revised_at TEXT")
        _runtime_add_column_if_missing(conn, "market_indicator_values", "collected_at", "collected_at TEXT")
        _runtime_add_column_if_missing(conn, "market_indicator_values", "revised_at", "revised_at TEXT")

        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_data_collection_policies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_type TEXT NOT NULL,
                item_code TEXT NOT NULL,
                frequency TEXT NOT NULL DEFAULT 'DAILY',
                initial_lookback_value INTEGER NOT NULL DEFAULT 2,
                initial_lookback_unit TEXT NOT NULL DEFAULT 'YEARS',
                overlap_value INTEGER NOT NULL DEFAULT 10,
                overlap_unit TEXT NOT NULL DEFAULT 'DAYS',
                minimum_refresh_interval_hours INTEGER NOT NULL DEFAULT 0,
                max_retry_count INTEGER NOT NULL DEFAULT 1,
                timeout_seconds INTEGER NOT NULL DEFAULT 30,
                is_auto_collect INTEGER NOT NULL DEFAULT 1,
                is_active INTEGER NOT NULL DEFAULT 1,
                last_attempt_at TEXT,
                last_success_at TEXT,
                last_status TEXT,
                last_error_type TEXT,
                last_error_message TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(item_type, item_code)
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_data_collection_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                finished_at TEXT,
                target_count INTEGER NOT NULL DEFAULT 0,
                success_count INTEGER NOT NULL DEFAULT 0,
                inserted_count INTEGER NOT NULL DEFAULT 0,
                updated_count INTEGER NOT NULL DEFAULT 0,
                unchanged_count INTEGER NOT NULL DEFAULT 0,
                skipped_count INTEGER NOT NULL DEFAULT 0,
                failed_count INTEGER NOT NULL DEFAULT 0,
                elapsed_ms INTEGER NOT NULL DEFAULT 0,
                triggered_by TEXT,
                error_summary TEXT
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_data_collection_run_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                item_type TEXT NOT NULL,
                item_code TEXT NOT NULL,
                provider_code TEXT,
                status TEXT NOT NULL,
                requested_from TEXT,
                requested_to TEXT,
                received_count INTEGER NOT NULL DEFAULT 0,
                inserted_count INTEGER NOT NULL DEFAULT 0,
                updated_count INTEGER NOT NULL DEFAULT 0,
                unchanged_count INTEGER NOT NULL DEFAULT 0,
                http_status INTEGER,
                provider_error_code TEXT,
                error_type TEXT,
                error_message TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                elapsed_ms INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (run_id) REFERENCES market_data_collection_runs(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_indicator_derivations (
                indicator_code TEXT PRIMARY KEY,
                formula_type TEXT NOT NULL,
                source_codes_json TEXT NOT NULL,
                parameters_json TEXT NOT NULL DEFAULT '{}',
                output_frequency TEXT NOT NULL DEFAULT 'DAILY',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (indicator_code) REFERENCES market_indicators(indicator_code) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_market_data_collection_runs_started ON market_data_collection_runs(started_at)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_market_data_collection_run_items_run ON market_data_collection_run_items(run_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_market_data_collection_run_items_code ON market_data_collection_run_items(item_type, item_code)")
        conn.exec_driver_sql("UPDATE market_indicator_values SET raw_payload_json = NULL WHERE raw_payload_json IS NOT NULL")
        conn.exec_driver_sql(
            """
            INSERT OR IGNORE INTO market_data_collection_policies
            (item_type, item_code, frequency, initial_lookback_value, initial_lookback_unit, overlap_value, overlap_unit,
             minimum_refresh_interval_hours, max_retry_count, timeout_seconds, is_auto_collect, is_active)
            SELECT 'INDEX', index_code, 'DAILY', 2, 'YEARS', 10, 'DAYS', 0, 1, 60, 1, is_active
            FROM market_indexes
            """
        )
        conn.exec_driver_sql(
            """
            INSERT OR IGNORE INTO market_data_collection_policies
            (item_type, item_code, frequency, initial_lookback_value, initial_lookback_unit, overlap_value, overlap_unit,
             minimum_refresh_interval_hours, max_retry_count, timeout_seconds, is_auto_collect, is_active)
            SELECT 'INDICATOR', indicator_code, data_frequency, 5, 'YEARS',
                   CASE UPPER(data_frequency) WHEN 'MONTHLY' THEN 6 WHEN 'QUARTERLY' THEN 4 WHEN 'WEEKLY' THEN 6 ELSE 10 END,
                   CASE UPPER(data_frequency) WHEN 'MONTHLY' THEN 'MONTHS' WHEN 'QUARTERLY' THEN 'QUARTERS' WHEN 'WEEKLY' THEN 'WEEKS' ELSE 'DAYS' END,
                   0, 1, 30, 1, is_active
            FROM market_indicators
            """
        )

        fred_rows = (
            ("US_30Y", "미국 국채 30년", "GLOBAL_RATE", "US_TREASURY", "DAILY", "LINE", "PCT", "%", "미국 30년 만기 국채의 Constant Maturity Rate. 미국 초장기 금리와 장기 기대 인플레이션, 기간 프리미엄 및 재정 부담 변화를 관찰하는 참고 지표.", 82, 3, "DGS30"),
            ("US_VIX", "VIX", "GLOBAL_RISK", "VOLATILITY", "DAILY", "LINE", "INDEX", "지수", "VIX risk-off and volatility signal", 90, 1, "VIXCLS"),
            ("US_REAL_10Y", "미국 10년 실질금리", "GLOBAL_RATE", "REAL_RATE", "DAILY", "LINE", "PCT", "%", "US 10Y real yield discount-rate pressure", 91, 2, "DFII10"),
            ("US_BREAKEVEN_10Y", "미국 10년 기대인플레이션", "INFLATION", "BREAKEVEN", "DAILY", "LINE", "PCT", "%", "US 10Y breakeven inflation expectation", 92, 3, "T10YIE"),
            ("US_NFCI", "Chicago Fed 금융여건지수", "CREDIT_LIQUIDITY", "FINANCIAL_CONDITIONS", "WEEKLY", "LINE", "INDEX", "지수", "Chicago Fed National Financial Conditions Index", 93, 4, "NFCI"),
            ("US_BROAD_DOLLAR", "미국 광의 달러지수", "FX", "DOLLAR", "DAILY", "LINE", "INDEX", "지수", "Trade weighted broad US dollar index", 94, 5, "DTWEXBGS"),
            ("WTI", "WTI 원유", "ENERGY", "OIL", "DAILY", "LINE", "USD", "달러", "WTI crude oil spot price", 95, 6, "DCOILWTICO"),
            ("US_CPI", "미국 CPI", "INFLATION", "US_CPI", "MONTHLY", "BAR_LINE", "INDEX", "지수", "US CPI index", 96, 7, "CPIAUCSL"),
            ("US_CORE_PCE", "미국 근원 PCE 물가지수", "INFLATION", "US_CORE_PCE", "MONTHLY", "BAR_LINE", "INDEX", "지수", "US core PCE price index", 97, 8, "PCEPILFE"),
            ("US_INITIAL_CLAIMS", "미국 신규 실업수당 청구", "EMPLOYMENT_CONSUMPTION", "CLAIMS", "WEEKLY", "LINE", "COUNT", "건", "Initial unemployment insurance claims", 98, 9, "ICSA"),
        )
        for row in fred_rows:
            conn.exec_driver_sql(
                """
                INSERT INTO market_indicators
                (indicator_code, indicator_name, category, subcategory, data_frequency, chart_type, unit, unit_label,
                 value_label, base_line_value, display_order, priority_rank, description, interpretation_note,
                 higher_value_meaning, lower_value_meaning, is_active, collection_status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, '발표값', NULL, ?, ?, ?, NULL, NULL, NULL, 1, 'WAITING', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(indicator_code) DO UPDATE SET
                    indicator_name = excluded.indicator_name,
                    category = excluded.category,
                    subcategory = excluded.subcategory,
                    data_frequency = excluded.data_frequency,
                    chart_type = excluded.chart_type,
                    unit = excluded.unit,
                    unit_label = excluded.unit_label,
                    display_order = excluded.display_order,
                    priority_rank = excluded.priority_rank,
                    description = excluded.description,
                    is_active = 1,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (*row[:8], row[9], row[10], row[8]),
            )
            request_params_json = json.dumps(
                {"series_id": row[11], "frequency": row[4][0].lower(), "value_field": "value", "date_field": "date", "scale": 1, "source_unit": row[6]},
                ensure_ascii=False,
                sort_keys=True,
            )
            conn.exec_driver_sql(
                """
                INSERT INTO market_indicator_provider_mappings
                (indicator_code, provider, api_type, api_id, endpoint_url, provider_symbol, request_params_json,
                 is_enabled, is_verified, last_test_status, last_test_message, created_at, updated_at)
                VALUES (?, 'FRED', 'SERIES_OBSERVATIONS', 'FRED_SERIES_OBSERVATIONS', '/fred/series/observations',
                        ?, ?, 1, 1, 'SUCCESS', 'FRED mapping seeded; collect endpoint validates data on run.', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(indicator_code, provider) DO UPDATE SET
                    api_type = excluded.api_type,
                    api_id = excluded.api_id,
                    endpoint_url = excluded.endpoint_url,
                    provider_symbol = excluded.provider_symbol,
                    request_params_json = excluded.request_params_json,
                    is_enabled = 1,
                    is_verified = 1,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (row[0], row[11], request_params_json),
            )
            conn.exec_driver_sql(
                """
                INSERT OR IGNORE INTO market_data_collection_policies
                (item_type, item_code, frequency, initial_lookback_value, initial_lookback_unit, overlap_value, overlap_unit,
                 minimum_refresh_interval_hours, max_retry_count, timeout_seconds, is_auto_collect, is_active)
                VALUES ('INDICATOR', ?, ?, 5, 'YEARS',
                        CASE ? WHEN 'MONTHLY' THEN 6 WHEN 'WEEKLY' THEN 6 ELSE 10 END,
                        CASE ? WHEN 'MONTHLY' THEN 'MONTHS' WHEN 'WEEKLY' THEN 'WEEKS' ELSE 'DAYS' END,
                        0, 1, 30, 1, 1)
                """,
                (row[0], row[4], row[4], row[4]),
            )


def ensure_market_signal_schema() -> None:
    if not DATABASE_URL.startswith("sqlite"):
        return

    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_signal_definitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_code TEXT NOT NULL UNIQUE,
                signal_name TEXT NOT NULL,
                description TEXT,
                category TEXT,
                signal_type TEXT NOT NULL DEFAULT 'COMPOSITE',
                horizon TEXT NOT NULL DEFAULT 'MEDIUM',
                status TEXT NOT NULL DEFAULT 'DRAFT',
                interpretation_direction TEXT NOT NULL DEFAULT 'MIXED',
                phenomenon_template TEXT,
                process_template TEXT,
                result_template TEXT,
                persistence_periods INTEGER NOT NULL DEFAULT 1,
                cooldown_periods INTEGER NOT NULL DEFAULT 0,
                minimum_data_quality REAL NOT NULL DEFAULT 60,
                current_version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_signal_conditions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_definition_id INTEGER NOT NULL,
                condition_group TEXT NOT NULL DEFAULT 'A',
                condition_role TEXT NOT NULL DEFAULT 'REQUIRED',
                item_type TEXT NOT NULL DEFAULT 'INDICATOR',
                item_code TEXT NOT NULL,
                transform_type TEXT NOT NULL DEFAULT 'RAW_VALUE',
                window_size INTEGER NOT NULL DEFAULT 20,
                comparison_operator TEXT NOT NULL DEFAULT '>',
                threshold_type TEXT NOT NULL DEFAULT 'ABSOLUTE',
                threshold_value REAL,
                threshold_secondary REAL,
                weight REAL NOT NULL DEFAULT 10,
                is_required INTEGER NOT NULL DEFAULT 0,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (signal_definition_id) REFERENCES market_signal_definitions(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_signal_evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_definition_id INTEGER NOT NULL,
                evaluated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                observation_date TEXT NOT NULL,
                state TEXT NOT NULL,
                score REAL NOT NULL DEFAULT 0,
                previous_score REAL,
                data_quality_score REAL NOT NULL DEFAULT 0,
                required_pass_count INTEGER NOT NULL DEFAULT 0,
                required_total_count INTEGER NOT NULL DEFAULT 0,
                confirm_pass_count INTEGER NOT NULL DEFAULT 0,
                opposing_pass_count INTEGER NOT NULL DEFAULT 0,
                phenomenon_text TEXT,
                process_text TEXT,
                result_text TEXT,
                evidence_json TEXT NOT NULL DEFAULT '[]',
                opposing_evidence_json TEXT NOT NULL DEFAULT '[]',
                missing_data_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(signal_definition_id, observation_date),
                FOREIGN KEY (signal_definition_id) REFERENCES market_signal_definitions(id) ON DELETE CASCADE
            )
            """
        )
        evaluation_columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(market_signal_evaluations)").fetchall()}
        if "evaluation_type" not in evaluation_columns:
            # Rebuild once so baseline and later evaluation types can coexist; legacy rows are copied intact.
            conn.exec_driver_sql(
                """
                CREATE TABLE market_signal_evaluations_v2 (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_definition_id INTEGER NOT NULL,
                    trend_model_id INTEGER,
                    evaluated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    observation_date TEXT NOT NULL,
                    evaluation_type TEXT NOT NULL DEFAULT 'PERIODIC',
                    rule_version INTEGER NOT NULL DEFAULT 1,
                    state TEXT NOT NULL,
                    previous_state TEXT,
                    current_state TEXT,
                    direction_state TEXT,
                    score REAL NOT NULL DEFAULT 0,
                    previous_score REAL,
                    current_value REAL,
                    trend_strength REAL,
                    channel_position REAL,
                    duration_count INTEGER NOT NULL DEFAULT 0,
                    normalized_slope REAL,
                    r_squared REAL,
                    data_quality_score REAL NOT NULL DEFAULT 0,
                    data_quality TEXT,
                    required_pass_count INTEGER NOT NULL DEFAULT 0,
                    required_total_count INTEGER NOT NULL DEFAULT 0,
                    confirm_pass_count INTEGER NOT NULL DEFAULT 0,
                    opposing_pass_count INTEGER NOT NULL DEFAULT 0,
                    phenomenon_text TEXT,
                    process_text TEXT,
                    result_text TEXT,
                    easy_explanation TEXT,
                    evaluation_reason TEXT,
                    evidence_json TEXT NOT NULL DEFAULT '[]',
                    opposing_evidence_json TEXT NOT NULL DEFAULT '[]',
                    missing_data_json TEXT NOT NULL DEFAULT '[]',
                    collection_run_id INTEGER,
                    is_state_transition INTEGER NOT NULL DEFAULT 0,
                    is_live INTEGER NOT NULL DEFAULT 1,
                    error_message TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(signal_definition_id, rule_version, observation_date, evaluation_type),
                    FOREIGN KEY (signal_definition_id) REFERENCES market_signal_definitions(id) ON DELETE CASCADE
                )
                """
            )
            conn.exec_driver_sql(
                """
                INSERT INTO market_signal_evaluations_v2
                (id, signal_definition_id, evaluated_at, observation_date, evaluation_type, rule_version,
                 state, current_state, score, previous_score, data_quality_score,
                 required_pass_count, required_total_count, confirm_pass_count, opposing_pass_count,
                 phenomenon_text, process_text, result_text, evidence_json, opposing_evidence_json,
                 missing_data_json, is_live, created_at)
                SELECT id, signal_definition_id, evaluated_at, observation_date, 'LEGACY', 1,
                       state, state, score, previous_score, data_quality_score,
                       required_pass_count, required_total_count, confirm_pass_count, opposing_pass_count,
                       phenomenon_text, process_text, result_text, evidence_json, opposing_evidence_json,
                       missing_data_json, 1, created_at
                FROM market_signal_evaluations
                """
            )
            conn.exec_driver_sql("DROP TABLE market_signal_evaluations")
            conn.exec_driver_sql("ALTER TABLE market_signal_evaluations_v2 RENAME TO market_signal_evaluations")
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_signal_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_definition_id INTEGER NOT NULL,
                event_date TEXT NOT NULL,
                previous_state TEXT,
                new_state TEXT NOT NULL,
                previous_score REAL,
                new_score REAL NOT NULL DEFAULT 0,
                event_type TEXT NOT NULL,
                summary TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(signal_definition_id, event_date, event_type),
                FOREIGN KEY (signal_definition_id) REFERENCES market_signal_definitions(id) ON DELETE CASCADE
            )
            """
        )
        event_columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(market_signal_events)").fetchall()}
        event_additions = {
            "evaluation_id": "INTEGER",
            "rule_version": "INTEGER NOT NULL DEFAULT 1",
            "observation_date": "TEXT",
            "is_live": "INTEGER NOT NULL DEFAULT 1",
        }
        for column_name, column_type in event_additions.items():
            if column_name not in event_columns:
                conn.exec_driver_sql(f"ALTER TABLE market_signal_events ADD COLUMN {column_name} {column_type}")
        conn.exec_driver_sql("UPDATE market_signal_events SET observation_date = event_date WHERE observation_date IS NULL")
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_signal_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_definition_id INTEGER NOT NULL,
                version_no INTEGER NOT NULL,
                snapshot_json TEXT NOT NULL,
                change_reason TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(signal_definition_id, version_no),
                FOREIGN KEY (signal_definition_id) REFERENCES market_signal_definitions(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_market_signal_definitions_status ON market_signal_definitions(status)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_market_signal_conditions_definition ON market_signal_conditions(signal_definition_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_market_signal_evaluations_signal_date ON market_signal_evaluations(signal_definition_id, observation_date)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_market_signal_evaluations_live_type ON market_signal_evaluations(signal_definition_id, is_live, evaluation_type)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_market_signal_conditions_dependency ON market_signal_conditions(item_type, item_code, signal_definition_id)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_market_signal_events_date ON market_signal_events(event_date)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_market_signal_events_live_state ON market_signal_events(signal_definition_id, is_live, new_state)")

        # Compact current-state projection. Do not add condition payloads,
        # chart series, provider responses, or per-day snapshots here.
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_signal_current_states (
                signal_definition_id INTEGER PRIMARY KEY,
                signal_version_id INTEGER NOT NULL,
                previous_state TEXT,
                current_state TEXT NOT NULL,
                evaluated_at TEXT NOT NULL,
                effective_date TEXT,
                last_transition_at TEXT,
                last_transition_from TEXT,
                last_transition_to TEXT,
                evaluation_status TEXT NOT NULL DEFAULT 'NOT_EVALUATED',
                missing_reason TEXT,
                error_message TEXT,
                collection_run_id INTEGER,
                trigger_type TEXT NOT NULL DEFAULT 'MANUAL',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (signal_definition_id) REFERENCES market_signal_definitions(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS idx_market_signal_current_transition ON market_signal_current_states(last_transition_at, evaluation_status)"
        )

        signal_columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(market_signal_definitions)").fetchall()}
        definition_additions = {
            "display_signal_level": "TEXT",
            "phenomenon_code": "TEXT",
            "relation_type": "TEXT",
            "confirmation_window": "INTEGER NOT NULL DEFAULT 5",
            "minimum_confirm_count": "INTEGER NOT NULL DEFAULT 1",
            "maximum_confirm_delay": "INTEGER NOT NULL DEFAULT 5",
            "order_required": "INTEGER NOT NULL DEFAULT 0",
            "minimum_confirm_persistence": "INTEGER NOT NULL DEFAULT 1",
            "evidence_group_code": "TEXT",
            "evidence_group_max_score": "REAL",
            "duplicate_weight_cap": "REAL",
            "validation_status": "TEXT NOT NULL DEFAULT 'UNVALIDATED'",
            "validation_period_years": "INTEGER",
            "validation_completed_at": "TEXT",
            "validation_summary_json": "TEXT NOT NULL DEFAULT '{}'",
            "activation_ready": "INTEGER NOT NULL DEFAULT 0",
            "activated_at": "TEXT",
            "activation_reason": "TEXT",
            "deactivated_at": "TEXT",
            "deactivation_reason": "TEXT",
        }
        for column_name, column_type in definition_additions.items():
            if column_name not in signal_columns:
                conn.exec_driver_sql(f"ALTER TABLE market_signal_definitions ADD COLUMN {column_name} {column_type}")

        # Keep only durable aggregate validation metrics. Detailed samples and
        # chart series belong to transient simulation responses, not SQLite.
        validation_rows = conn.exec_driver_sql(
            "SELECT id, validation_summary_json FROM market_signal_definitions WHERE length(validation_summary_json) > 2"
        ).fetchall()
        for definition_id, raw_summary in validation_rows:
            try:
                parsed_summary = json.loads(raw_summary or "{}")
            except (TypeError, json.JSONDecodeError):
                parsed_summary = {}
            compact_json = json.dumps(
                compact_validation_summary(parsed_summary),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            if compact_json != (raw_summary or "{}"):
                conn.exec_driver_sql(
                    "UPDATE market_signal_definitions SET validation_summary_json = ? WHERE id = ?",
                    (compact_json, definition_id),
                )

        condition_columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(market_signal_conditions)").fetchall()}
        condition_additions = {
            "relation_type": "TEXT",
            "confirmation_window": "INTEGER",
            "evidence_group_code": "TEXT",
            "evidence_group_max_score": "REAL",
            "duplicate_weight_cap": "REAL",
        }
        for column_name, column_type in condition_additions.items():
            if column_name not in condition_columns:
                conn.exec_driver_sql(f"ALTER TABLE market_signal_conditions ADD COLUMN {column_name} {column_type}")

        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_signal_trend_models (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_definition_id INTEGER,
                item_type TEXT NOT NULL DEFAULT 'INDICATOR',
                item_code TEXT NOT NULL,
                model_type TEXT NOT NULL DEFAULT 'REGRESSION_CHANNEL',
                short_window INTEGER NOT NULL DEFAULT 20,
                medium_window INTEGER NOT NULL DEFAULT 60,
                trend_window INTEGER NOT NULL DEFAULT 120,
                minimum_trend_duration INTEGER NOT NULL DEFAULT 20,
                channel_multiplier REAL NOT NULL DEFAULT 2.0,
                minimum_break_distance REAL NOT NULL DEFAULT 0.15,
                minimum_break_persistence INTEGER NOT NULL DEFAULT 2,
                reversal_persistence INTEGER NOT NULL DEFAULT 3,
                false_break_window INTEGER NOT NULL DEFAULT 5,
                minimum_trend_strength REAL NOT NULL DEFAULT 1.0,
                minimum_r_squared REAL NOT NULL DEFAULT 0.18,
                volatility_window INTEGER NOT NULL DEFAULT 20,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(signal_definition_id, item_type, item_code),
                FOREIGN KEY (signal_definition_id) REFERENCES market_signal_definitions(id) ON DELETE CASCADE
            )
            """
        )
        trend_columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(market_signal_trend_models)").fetchall()}
        if "model_profile_code" not in trend_columns:
            conn.exec_driver_sql("ALTER TABLE market_signal_trend_models ADD COLUMN model_profile_code TEXT NOT NULL DEFAULT 'MARKET_PRICE_TREND'")
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_signal_evidence_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_code TEXT NOT NULL UNIQUE,
                source_name TEXT NOT NULL,
                source_type TEXT NOT NULL DEFAULT 'INDICATOR',
                item_type TEXT,
                item_code TEXT,
                provider TEXT,
                evidence_group_code TEXT,
                reliability_score REAL NOT NULL DEFAULT 1.0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_signal_model_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_code TEXT NOT NULL UNIQUE,
                profile_name TEXT NOT NULL,
                description TEXT,
                applicable_categories_json TEXT NOT NULL DEFAULT '[]',
                applicable_frequencies_json TEXT NOT NULL DEFAULT '[]',
                default_configuration_json TEXT NOT NULL DEFAULT '{}',
                supported_transforms_json TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_signal_episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phenomenon_definition_id INTEGER NOT NULL,
                phenomenon_code TEXT NOT NULL,
                trigger_date TEXT,
                first_confirm_date TEXT,
                release_date TEXT,
                state TEXT NOT NULL DEFAULT 'CANDIDATE',
                peak_score REAL,
                latest_score REAL,
                data_quality_score REAL,
                applied_rule_version INTEGER NOT NULL DEFAULT 1,
                timeline_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(phenomenon_definition_id, trigger_date, applied_rule_version),
                FOREIGN KEY (phenomenon_definition_id) REFERENCES market_signal_definitions(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_signal_episode_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                episode_id INTEGER NOT NULL,
                outcome_date TEXT,
                outcome_type TEXT NOT NULL,
                outcome_value REAL,
                outcome_note TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (episode_id) REFERENCES market_signal_episodes(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_signal_user_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_definition_id INTEGER,
                episode_id INTEGER,
                review_target_type TEXT NOT NULL DEFAULT 'PHENOMENON',
                review_target_id INTEGER,
                reviewer TEXT,
                review_status TEXT NOT NULL DEFAULT 'PENDING',
                usefulness_score REAL,
                accuracy_score REAL,
                review_note TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (signal_definition_id) REFERENCES market_signal_definitions(id) ON DELETE SET NULL,
                FOREIGN KEY (episode_id) REFERENCES market_signal_episodes(id) ON DELETE SET NULL
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_signal_rule_experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_definition_id INTEGER,
                experiment_code TEXT NOT NULL UNIQUE,
                experiment_name TEXT NOT NULL,
                experiment_type TEXT NOT NULL DEFAULT 'CHALLENGER',
                status TEXT NOT NULL DEFAULT 'DRAFT',
                hypothesis TEXT,
                proposed_rule_json TEXT NOT NULL DEFAULT '{}',
                validation_summary_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (signal_definition_id) REFERENCES market_signal_definitions(id) ON DELETE SET NULL
            )
            """
        )
        experiment_validation_rows = conn.exec_driver_sql(
            "SELECT id, validation_summary_json FROM market_signal_rule_experiments WHERE length(validation_summary_json) > 2"
        ).fetchall()
        for experiment_id, raw_summary in experiment_validation_rows:
            try:
                parsed_summary = json.loads(raw_summary or "{}")
            except (TypeError, json.JSONDecodeError):
                parsed_summary = {}
            compact_json = json.dumps(
                compact_validation_summary(parsed_summary),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            if compact_json != (raw_summary or "{}"):
                conn.exec_driver_sql(
                    "UPDATE market_signal_rule_experiments SET validation_summary_json = ? WHERE id = ?",
                    (compact_json, experiment_id),
                )

        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_signal_rule_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_code TEXT NOT NULL UNIQUE,
                template_name TEXT NOT NULL,
                signal_level TEXT NOT NULL DEFAULT 'SINGLE_INDICATOR',
                category TEXT,
                description TEXT,
                difficulty TEXT NOT NULL DEFAULT 'BASIC',
                configuration_json TEXT NOT NULL DEFAULT '{}',
                required_indicator_codes_json TEXT NOT NULL DEFAULT '[]',
                recommended_horizon TEXT NOT NULL DEFAULT 'MEDIUM',
                evidence_summary TEXT,
                status TEXT NOT NULL DEFAULT 'DRAFT',
                usage_count INTEGER NOT NULL DEFAULT 0,
                copied_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_market_signal_trend_models_item ON market_signal_trend_models(item_type, item_code)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_market_signal_trend_models_profile ON market_signal_trend_models(model_profile_code)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_market_signal_episodes_code_state ON market_signal_episodes(phenomenon_code, state)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_market_signal_rule_templates_level ON market_signal_rule_templates(signal_level, status)")

        profile_rows = (
            ("MARKET_PRICE_TREND", "시장가격 추세형", "주가지수와 업종지수의 회귀 채널 추세 모델", '["MARKET_INDEX","GLOBAL_INDEX"]', '["DAILY"]', {"short_window": 20, "medium_window": 60, "trend_window": 120, "channel_multiplier": 1.8, "minimum_break_persistence": 3, "false_break_window": 5, "reversal_persistence": 5}, ["TREND_STATE", "TREND_STRENGTH", "CHANNEL_POSITION", "BREAK_CONFIRMED_UP", "BREAK_CONFIRMED_DOWN", "FALSE_BREAK_UP", "FALSE_BREAK_DOWN"]),
            ("FX_TREND", "환율 추세형", "환율과 달러지수의 변동성 조정 추세 모델", '["FX"]', '["DAILY"]', {"short_window": 20, "medium_window": 60, "trend_window": 120, "channel_multiplier": 2.0, "minimum_break_persistence": 2, "false_break_window": 5}, ["TREND_STATE", "NORMALIZED_SLOPE", "CHANNEL_POSITION", "TREND_BREAK_UP", "TREND_BREAK_DOWN"]),
            ("YIELD_TREND", "금리 추세형", "국내외 시장금리 추세와 반전 모델", '["RATE","GLOBAL_RATE"]', '["DAILY"]', {"short_window": 20, "medium_window": 60, "trend_window": 120, "channel_multiplier": 1.7, "minimum_break_persistence": 2}, ["TREND_STATE", "REGRESSION_SLOPE", "TREND_STRENGTH", "REVERSAL_CONFIRMED_UP", "REVERSAL_CONFIRMED_DOWN"]),
            ("POLICY_RATE_REGIME", "정책금리 국면형", "정책금리 변경 방향과 동결 기간 중심 모델", '["RATE","GLOBAL_RATE"]', '["MONTHLY","DAILY"]', {"short_window": 6, "medium_window": 12, "trend_window": 36, "channel_multiplier": 1.0, "minimum_break_persistence": 1}, ["CHANGE", "TREND_STATE", "TREND_DURATION"]),
            ("MACRO_MOM_YOY_TREND", "물가 추세형", "월간 물가 지표의 MoM/YoY 추세 모델", '["INFLATION","ECONOMY"]', '["MONTHLY"]', {"short_window": 6, "medium_window": 12, "trend_window": 36, "channel_multiplier": 1.5, "minimum_break_persistence": 2}, ["MOM", "YOY", "TREND_STATE", "TREND_STRENGTH"]),
            ("SENTIMENT_TREND", "심리 추세형", "소비자·기업 심리 지표의 6/12개월 추세 모델", '["ECONOMY","CREDIT_LIQUIDITY","EMPLOYMENT_CONSUMPTION"]', '["MONTHLY","WEEKLY"]', {"short_window": 6, "medium_window": 12, "trend_window": 36, "channel_multiplier": 1.6}, ["TREND_STATE", "NORMALIZED_SLOPE", "TREND_DURATION"]),
            ("RELATIVE_STRENGTH", "상대강도형", "시장 대비 상대강도 추세와 이탈 모델", '["DERIVED"]', '["DAILY"]', {"short_window": 20, "medium_window": 60, "trend_window": 120, "channel_multiplier": 1.8}, ["RELATIVE_STRENGTH", "TREND_STATE", "CHANNEL_POSITION", "BREAK_CONFIRMED_UP", "BREAK_CONFIRMED_DOWN"]),
            ("VOLATILITY_REGIME", "변동성 국면형", "변동성 체제와 고변동성 전환 모델", '["GLOBAL_RISK","DERIVED"]', '["DAILY"]', {"short_window": 20, "medium_window": 60, "trend_window": 120, "channel_multiplier": 2.2}, ["Z_SCORE", "PERCENTILE", "TREND_STATE", "TREND_BREAK_UP"]),
            ("SPREAD_REGIME", "스프레드 국면형", "금리차와 실질금리 스프레드의 방향·역전 모델", '["DERIVED"]', '["DAILY","MONTHLY"]', {"short_window": 20, "medium_window": 60, "trend_window": 120, "channel_multiplier": 1.7}, ["SPREAD", "TREND_STATE", "CHANNEL_POSITION", "REVERSAL_CONFIRMED_UP", "REVERSAL_CONFIRMED_DOWN"]),
            ("COMMODITY_TREND", "원자재 추세형", "금·유가 등 원자재 가격 추세와 반전 모델", '["ENERGY","COMMODITY"]', '["DAILY"]', {"short_window": 20, "medium_window": 60, "trend_window": 120, "channel_multiplier": 2.0}, ["TREND_STATE", "TREND_STRENGTH", "CHANNEL_POSITION", "FALSE_BREAK_UP", "FALSE_BREAK_DOWN"]),
        )
        for profile in profile_rows:
            conn.exec_driver_sql(
                """
                INSERT INTO market_signal_model_profiles
                (profile_code, profile_name, description, applicable_categories_json, applicable_frequencies_json,
                 default_configuration_json, supported_transforms_json, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE')
                ON CONFLICT(profile_code) DO UPDATE SET
                    profile_name = excluded.profile_name,
                    description = excluded.description,
                    applicable_categories_json = excluded.applicable_categories_json,
                    applicable_frequencies_json = excluded.applicable_frequencies_json,
                    default_configuration_json = excluded.default_configuration_json,
                    supported_transforms_json = excluded.supported_transforms_json,
                    status = 'ACTIVE',
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    profile[0],
                    profile[1],
                    profile[2],
                    profile[3],
                    profile[4],
                    json.dumps(profile[5], ensure_ascii=False, sort_keys=True),
                    json.dumps(profile[6], ensure_ascii=False, sort_keys=True),
                ),
            )

        template_rows = (
            ("US_REAL_RATE_TURN_UP", "미국 실질금리 상승 전환", "SINGLE_INDICATOR", "금리·성장주", "미국 10년 실질금리가 상승 추세로 전환되는지 봅니다.", "BASIC", '["US_REAL_10Y"]', "MEDIUM", "실질금리 상승은 성장주 할인율 부담을 키울 수 있습니다."),
            ("US_10Y_UP_BREAK", "미국 장기금리 상승 추세 확인", "SINGLE_INDICATOR", "금리·성장주", "미국 10년 금리가 상승 추세와 채널 이탈을 보이는지 봅니다.", "BASIC", '["US_10Y"]', "MEDIUM", "장기금리 상승 추세는 위험자산 밸류에이션 부담으로 연결될 수 있습니다."),
            ("NASDAQ_RELATIVE_WEAKENING", "NASDAQ 상대강도 약화", "SINGLE_INDICATOR", "금리·성장주", "NASDAQ/S&P500 상대강도 하락 전환을 봅니다.", "BASIC", '["NASDAQ_SP500_RELATIVE"]', "MEDIUM", "성장주 상대강도 약화 여부를 확인합니다."),
            ("SOX_RELATIVE_TURN_DOWN", "SOX 상대강도 하락 전환", "SINGLE_INDICATOR", "반도체", "SOX/S&P500 상대강도 하락 전환을 봅니다.", "BASIC", '["SOX_SP500_RELATIVE"]', "MEDIUM", "반도체 선호 약화 여부를 확인합니다."),
            ("VIX_TURN_UP", "VIX 상승 추세 전환", "SINGLE_INDICATOR", "위험신호", "VIX가 안정 구간에서 상승 전환하는지 봅니다.", "BASIC", '["US_VIX"]', "SHORT", "변동성 확대 초기 신호로 사용합니다."),
            ("NFCI_TIGHTENING_TURN", "금융여건 긴축 전환", "SINGLE_INDICATOR", "위험신호", "Chicago Fed 금융여건지수의 긴축 전환을 봅니다.", "BASIC", '["US_NFCI"]', "SHORT", "금융여건 악화가 위험회피와 연결되는지 확인합니다."),
            ("BROAD_DOLLAR_RISK_PRESSURE", "달러 강세와 위험자산 부담", "COMPOSITE_INDICATOR", "달러·환율", "달러 강세와 위험자산 약화가 동시에 나타나는지 봅니다.", "INTERMEDIATE", '["US_BROAD_DOLLAR","NASDAQ_SP500_RELATIVE","US_VIX"]', "SHORT", "달러 강세와 주식 상대강도 약화의 동시성을 확인합니다."),
            ("WTI_TURN_UP", "WTI 상승 추세 전환", "SINGLE_INDICATOR", "물가", "WTI가 상승 추세로 전환되는지 봅니다.", "BASIC", '["WTI"]', "MEDIUM", "에너지 가격이 물가 기대를 자극하는지 확인합니다."),
            ("BREAKEVEN_TURN_UP", "기대인플레이션 상승 전환", "SINGLE_INDICATOR", "물가", "미국 10년 기대인플레이션 상승 전환을 봅니다.", "BASIC", '["US_BREAKEVEN_10Y"]', "MEDIUM", "물가 기대의 재상승 여부를 확인합니다."),
            ("CPI_DISINFLATION_SLOWING", "CPI 둔화 추세 약화", "SINGLE_INDICATOR", "물가", "CPI 둔화 속도가 느려지는지 봅니다.", "INTERMEDIATE", '["US_CPI"]', "MEDIUM", "디스인플레이션 둔화 여부를 확인합니다."),
            ("INITIAL_CLAIMS_4W_UP", "신규 실업수당 4주 평균 상승", "SINGLE_INDICATOR", "고용·경기", "신규 실업수당 청구의 상승 전환을 봅니다.", "BASIC", '["US_INITIAL_CLAIMS"]', "SHORT", "고용 안정에서 둔화로 넘어가는 초기 신호입니다."),
            ("US_RATE_GROWTH_PRESSURE", "미국 실질금리와 성장주 부담", "COMPOSITE_INDICATOR", "금리·성장주", "실질금리 상승과 성장주 상대강도 약화를 함께 봅니다.", "INTERMEDIATE", '["US_REAL_10Y","US_10Y","NASDAQ_SP500_RELATIVE"]', "MEDIUM", "금리 상승 후 성장주 상대강도 약화가 확인되는지 봅니다."),
            ("GLOBAL_RISK_OFF_TURN", "글로벌 위험회피 전환", "COMPOSITE_INDICATOR", "위험신호", "VIX, 금융여건, 달러, 상대강도를 함께 봅니다.", "INTERMEDIATE", '["US_VIX","US_NFCI","US_BROAD_DOLLAR","NASDAQ_SP500_RELATIVE"]', "SHORT", "위험선호에서 위험회피로 넘어가는 복합 신호입니다."),
            ("REFLATION_WARNING", "리플레이션 전환 후보", "COMPOSITE_INDICATOR", "물가", "WTI, 기대인플레이션, CPI/PCE를 함께 봅니다.", "INTERMEDIATE", '["WTI","US_BREAKEVEN_10Y","US_CPI","US_CORE_PCE"]', "MEDIUM", "물가 재상승 압력이 확인되는지 봅니다."),
            ("US_EMPLOYMENT_WEAKENING", "미국 고용 둔화 후보", "COMPOSITE_INDICATOR", "고용·경기", "실업수당 청구, 금리차, 주가지수를 함께 봅니다.", "INTERMEDIATE", '["US_INITIAL_CLAIMS","US_10Y_2Y_SPREAD","US_SP500"]', "SHORT", "고용 둔화 후보를 객관적 현상으로 연결합니다."),
            ("KOREA_SEMICONDUCTOR_CONTEXT", "미국 SOX와 국내 반도체 환경", "COMPOSITE_INDICATOR", "한국시장", "SOX 상대강도와 국내 반도체 환경을 함께 봅니다.", "ADVANCED", '["SOX_SP500_RELATIVE","KOSPI","KOSDAQ"]', "MEDIUM", "미국 반도체 신호가 국내 시장에 주는 배경 조건입니다."),
            ("KR_STOCK_RISK_OFF_TURN", "국내 주식시장 위험회피 전환", "COMPOSITE_INDICATOR", "한국시장", "KOSPI, KOSDAQ, 환율, 변동성을 함께 보며 국내 위험회피 전환을 봅니다.", "INTERMEDIATE", '["KOSPI","KOSDAQ","USD_KRW","USD_KRW_VOLATILITY"]', "SHORT", "국내 주가지수 약화와 환율·변동성 압력이 겹치는지 확인합니다."),
            ("USD_KRW_UP_PRESSURE", "원/달러 상승 압력", "COMPOSITE_INDICATOR", "환율", "원/달러, 달러지수, 국내 금리 환경을 함께 보며 환율 상승 압력을 봅니다.", "INTERMEDIATE", '["USD_KRW","US_BROAD_DOLLAR","KTB_10Y"]', "SHORT", "달러 강세와 국내 장기금리 환경이 원화 약세 압력으로 이어지는지 확인합니다."),
            ("KR_LONG_RATE_PRESSURE", "국내 장기금리 상승 압력", "COMPOSITE_INDICATOR", "국내금리", "국고채 10년, 3년, 기준금리와 장단기 스프레드를 함께 봅니다.", "INTERMEDIATE", '["KTB_10Y","KTB_3Y","BASE_RATE","KR_10Y_3Y_SPREAD"]', "MEDIUM", "국내 장기금리 상승 압력과 커브 변화를 객관적으로 확인합니다."),
            ("KR_SENTIMENT_WEAKENING", "국내 심리 약화", "COMPOSITE_INDICATOR", "물가·경기", "소비자심리지수와 제조업 업황BSI 약화를 함께 봅니다.", "BASIC", '["CSI","BSI_MANUFACTURING"]', "MEDIUM", "심리지표가 동반 약화되는지 확인합니다."),
            ("KR_SEMICONDUCTOR_CONTEXT_WEAKENING", "국내 반도체 맥락 약화", "COMPOSITE_INDICATOR", "한국시장", "미국 SOX 상대강도와 국내 대표지수를 함께 보며 반도체 환경 약화를 봅니다.", "ADVANCED", '["SOX_SP500_RELATIVE","KOSPI","KOSDAQ","KRX100"]', "MEDIUM", "미국 반도체 약세가 국내 시장 맥락 약화와 같이 나타나는지 봅니다."),
            ("KR_REAL_TIGHTENING_ENVIRONMENT", "국내 실질 긴축 환경", "COMPOSITE_INDICATOR", "국내금리", "실질정책금리, 기준금리, 물가를 함께 보며 국내 실질 긴축 환경을 봅니다.", "INTERMEDIATE", '["KR_REAL_POLICY_RATE","BASE_RATE","CPI"]', "MEDIUM", "물가 대비 정책금리 부담이 커지는지 확인합니다."),
        )
        for template in template_rows:
            configuration = {
                "signal_level": template[2],
                "suggested_roles": {
                    "trigger": json.loads(template[6])[:1],
                    "confirm": json.loads(template[6])[1:],
                    "opposing": [],
                    "invalidation": [],
                },
                "default_transform": "TREND_STATE",
                "confirmation_window": 10,
                "persistence_periods": 2,
            }
            conn.exec_driver_sql(
                """
                INSERT INTO market_signal_rule_templates
                (template_code, template_name, signal_level, category, description, difficulty, configuration_json,
                 required_indicator_codes_json, recommended_horizon, evidence_summary, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'DRAFT')
                ON CONFLICT(template_code) DO UPDATE SET
                    template_name = excluded.template_name,
                    signal_level = excluded.signal_level,
                    category = excluded.category,
                    description = excluded.description,
                    difficulty = excluded.difficulty,
                    configuration_json = excluded.configuration_json,
                    required_indicator_codes_json = excluded.required_indicator_codes_json,
                    recommended_horizon = excluded.recommended_horizon,
                    evidence_summary = excluded.evidence_summary,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (*template[:6], json.dumps(configuration, ensure_ascii=False, sort_keys=True), template[6], template[7], template[8]),
            )

        seed_signals = (
            (
                "US_REAL_RATE_GROWTH_PRESSURE",
                "미국 실질금리 상승과 성장주 부담",
                "미국 실질금리와 장기금리 상승 전환이 성장주 상대강도를 약화시키는지 관찰합니다.",
                "US_RATE_GROWTH",
                "MEDIUM",
                "MIXED",
                "미국 실질금리 상승 전환과 성장주 상대강도 둔화 가능성",
                "실질금리 상승은 미래 이익 할인율을 높이고 고평가 성장주의 밸류에이션 부담을 키울 수 있습니다.",
                "성장주 변동성 확대와 실적 가시성에 따른 종목 차별화 가능성",
            ),
            (
                "RISK_ON_TO_RISK_OFF_TURN",
                "위험선호에서 위험회피로의 전환",
                "VIX, 금융여건, 달러, 주식 상대강도를 함께 보며 위험회피 전환을 감지합니다.",
                "GLOBAL_RISK",
                "SHORT",
                "NEGATIVE",
                "변동성과 금융여건이 위험회피 쪽으로 기울 가능성",
                "변동성 상승과 금융여건 긴축은 위험자산 노출 축소와 성장주 중심 부담으로 이어질 수 있습니다.",
                "위험자산 변동성 확대와 방어적 포지셔닝 필요성 증가",
            ),
            (
                "DISINFLATION_TO_REFLATION_TURN",
                "물가 둔화에서 재상승으로의 전환",
                "WTI와 기대인플레이션, CPI/PCE 둔화를 함께 확인해 물가 재상승 전환을 관찰합니다.",
                "INFLATION_REFLATION",
                "MEDIUM",
                "MIXED",
                "에너지와 기대물가가 물가 재상승 압력을 만들 가능성",
                "원유와 기대인플레이션 상승은 금리 인하 기대를 약화시키고 장기금리 상승 압력을 높일 수 있습니다.",
                "금리 민감 자산 부담과 인플레이션 수혜 업종 선별 가능성",
            ),
            (
                "US_EMPLOYMENT_STABLE_TO_WEAKENING",
                "미국 고용 안정에서 둔화로의 전환",
                "신규 실업수당 청구와 경기 민감 지표를 통해 고용 둔화 전환을 관찰합니다.",
                "US_EMPLOYMENT",
                "SHORT",
                "NEGATIVE",
                "신규 실업수당 청구가 증가하며 고용 안정성이 약해지는지 확인",
                "고용 수요 둔화는 소비와 기업 매출 기대를 낮추며 통화완화 기대를 동시에 키울 수 있습니다.",
                "경기 둔화 우려와 금리 인하 기대가 같이 커지는 혼재 국면 가능성",
            ),
        )
        for signal in seed_signals:
            conn.exec_driver_sql(
                """
                INSERT INTO market_signal_definitions
                (signal_code, signal_name, description, category, signal_type, horizon, status, interpretation_direction,
                 phenomenon_template, process_template, result_template, persistence_periods, cooldown_periods, minimum_data_quality)
                VALUES (?, ?, ?, ?, 'COMPOSITE', ?, 'DRAFT', ?, ?, ?, ?, 2, 1, 50)
                ON CONFLICT(signal_code) DO NOTHING
                """,
                signal,
            )

        condition_seed = {
            "US_REAL_RATE_GROWTH_PRESSURE": [
                ("REQUIRED", "INDICATOR", "US_REAL_10Y", "TURN_UP", 20, ">", "ABSOLUTE", 0, None, 25, 1),
                ("REQUIRED", "INDICATOR", "US_10Y", "SLOPE", 20, ">", "ABSOLUTE", 0, None, 25, 1),
                ("CONFIRM", "INDICATOR", "US_BROAD_DOLLAR", "SLOPE", 20, ">", "ABSOLUTE", 0, None, 15, 0),
                ("CONFIRM", "INDICATOR", "NASDAQ_SP500_RELATIVE", "SLOPE", 20, "<", "ABSOLUTE", 0, None, 15, 0),
                ("OPPOSING", "INDICATOR", "US_VIX", "SLOPE", 10, "<=", "ABSOLUTE", 0, None, 10, 0),
            ],
            "RISK_ON_TO_RISK_OFF_TURN": [
                ("REQUIRED", "INDICATOR", "US_VIX", "TURN_UP", 10, ">", "ABSOLUTE", 0, None, 30, 1),
                ("REQUIRED", "INDICATOR", "US_NFCI", "SLOPE", 8, ">", "ABSOLUTE", 0, None, 20, 1),
                ("CONFIRM", "INDICATOR", "US_BROAD_DOLLAR", "SLOPE", 20, ">", "ABSOLUTE", 0, None, 15, 0),
                ("CONFIRM", "INDICATOR", "NASDAQ_SP500_RELATIVE", "SLOPE", 20, "<", "ABSOLUTE", 0, None, 15, 0),
                ("OPPOSING", "INDICATOR", "US_VIX", "CHANGE_RATE", 5, "<", "ABSOLUTE", 0, None, 10, 0),
            ],
            "DISINFLATION_TO_REFLATION_TURN": [
                ("REQUIRED", "INDICATOR", "WTI", "TURN_UP", 20, ">", "ABSOLUTE", 0, None, 25, 1),
                ("REQUIRED", "INDICATOR", "US_BREAKEVEN_10Y", "SLOPE", 20, ">", "ABSOLUTE", 0, None, 25, 1),
                ("CONFIRM", "INDICATOR", "US_CPI", "YOY", 12, ">", "ABSOLUTE", 0, None, 15, 0),
                ("CONFIRM", "INDICATOR", "US_CORE_PCE", "YOY", 12, ">", "ABSOLUTE", 0, None, 15, 0),
                ("OPPOSING", "INDICATOR", "US_REAL_10Y", "SLOPE", 20, "<", "ABSOLUTE", 0, None, 10, 0),
            ],
            "US_EMPLOYMENT_STABLE_TO_WEAKENING": [
                ("REQUIRED", "INDICATOR", "US_INITIAL_CLAIMS", "TURN_UP", 8, ">", "ABSOLUTE", 0, None, 35, 1),
                ("REQUIRED", "INDICATOR", "US_INITIAL_CLAIMS", "CONSECUTIVE_UP", 4, ">=", "ABSOLUTE", 2, None, 20, 1),
                ("CONFIRM", "INDICATOR", "US_10Y_2Y_SPREAD", "SLOPE", 20, "<", "ABSOLUTE", 0, None, 15, 0),
                ("CONFIRM", "INDICATOR", "US_SP500", "SLOPE", 20, "<", "ABSOLUTE", 0, None, 15, 0),
                ("OPPOSING", "INDICATOR", "US_NASDAQ", "SLOPE", 20, ">", "ABSOLUTE", 0, None, 10, 0),
            ],
        }
        for signal_code, rows in condition_seed.items():
            signal_id = conn.exec_driver_sql("SELECT id FROM market_signal_definitions WHERE signal_code = ?", (signal_code,)).scalar()
            if not signal_id:
                continue
            existing_count = conn.exec_driver_sql("SELECT COUNT(*) FROM market_signal_conditions WHERE signal_definition_id = ?", (signal_id,)).scalar() or 0
            if existing_count:
                continue
            for order, row in enumerate(rows, start=1):
                conn.exec_driver_sql(
                    """
                    INSERT INTO market_signal_conditions
                    (signal_definition_id, condition_group, condition_role, item_type, item_code, transform_type,
                     window_size, comparison_operator, threshold_type, threshold_value, threshold_secondary, weight, is_required, sort_order)
                    VALUES (?, 'A', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (signal_id, *row, order),
                )
            snapshot = conn.exec_driver_sql("SELECT * FROM market_signal_definitions WHERE id = ?", (signal_id,)).mappings().first()
            if snapshot:
                conn.exec_driver_sql(
                    """
                    INSERT OR IGNORE INTO market_signal_versions
                    (signal_definition_id, version_no, snapshot_json, change_reason)
                    VALUES (?, 1, ?, 'Initial MVP draft seed')
                    """,
                    (signal_id, json.dumps(dict(snapshot), ensure_ascii=False, sort_keys=True)),
                )

        derived_rows = (
            ("US_10Y_2Y_SPREAD", "미국 10년-2년 금리차", "DERIVED", "SPREAD", "DAILY", "LINE", "PP", "%p", "US_10Y_MINUS_US_2Y", '["US_10Y","US_2Y"]', 120),
            ("KR_10Y_3Y_SPREAD", "한국 10년-3년 금리차", "DERIVED", "SPREAD", "DAILY", "LINE", "PP", "%p", "KR_10Y_MINUS_KR_3Y", '["KTB_10Y","KTB_3Y"]', 121),
            ("KR_REAL_POLICY_RATE", "한국 실질 기준금리", "DERIVED", "REAL_RATE", "MONTHLY", "LINE", "PP", "%p", "BASE_RATE_MINUS_CPI_YOY", '["BASE_RATE","CPI"]', 122),
            ("US_REAL_POLICY_RATE", "미국 실질 정책금리", "DERIVED", "REAL_RATE", "MONTHLY", "LINE", "PP", "%p", "FED_FUNDS_MINUS_CORE_PCE_YOY", '["US_FED_FUNDS","US_CORE_PCE"]', 123),
            ("USD_KRW_VOLATILITY", "달러/원 20일 변동성", "DERIVED", "VOLATILITY", "DAILY", "LINE", "PCT", "%", "ROLLING_RETURN_STD_20D", '["USD_KRW"]', 124),
            ("NASDAQ_SP500_RELATIVE", "NASDAQ/S&P500 상대강도", "DERIVED", "RELATIVE_STRENGTH", "DAILY", "LINE", "INDEX", "지수", "RATIO_X100", '["US_NASDAQ","US_SP500"]', 125),
            ("SOX_SP500_RELATIVE", "SOX/S&P500 상대강도", "DERIVED", "RELATIVE_STRENGTH", "DAILY", "LINE", "INDEX", "지수", "RATIO_X100", '["US_SOX","US_SP500"]', 126),
        )
        for row in derived_rows:
            conn.exec_driver_sql(
                """
                INSERT INTO market_indicators
                (indicator_code, indicator_name, category, subcategory, data_frequency, chart_type, unit, unit_label,
                 value_label, base_line_value, display_order, priority_rank, description, interpretation_note,
                 higher_value_meaning, lower_value_meaning, is_active, collection_status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, '계산값', NULL, ?, 1, 'DrCT 내부 파생 지표', NULL, NULL, NULL, 1, 'WAITING', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(indicator_code) DO UPDATE SET
                    indicator_name = excluded.indicator_name,
                    category = excluded.category,
                    subcategory = excluded.subcategory,
                    data_frequency = excluded.data_frequency,
                    chart_type = excluded.chart_type,
                    unit = excluded.unit,
                    unit_label = excluded.unit_label,
                    display_order = excluded.display_order,
                    is_active = 1,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (*row[:8], row[10]),
            )
            conn.exec_driver_sql(
                """
                INSERT INTO market_indicator_provider_mappings
                (indicator_code, provider, api_type, api_id, endpoint_url, provider_symbol, request_params_json,
                 is_enabled, is_verified, last_test_status, last_test_message, created_at, updated_at)
                VALUES (?, 'DERIVED', 'DERIVED_FORMULA', ?, NULL, ?, '{}', 1, 1, 'SUCCESS', 'Derived formula is active.', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(indicator_code, provider) DO UPDATE SET
                    api_type = excluded.api_type,
                    api_id = excluded.api_id,
                    provider_symbol = excluded.provider_symbol,
                    is_enabled = 1,
                    is_verified = 1,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (row[0], row[8], row[8]),
            )
            conn.exec_driver_sql(
                """
                INSERT INTO market_indicator_derivations
                (indicator_code, formula_type, source_codes_json, parameters_json, output_frequency, is_active, created_at, updated_at)
                VALUES (?, ?, ?, '{}', ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(indicator_code) DO UPDATE SET
                    formula_type = excluded.formula_type,
                    source_codes_json = excluded.source_codes_json,
                    output_frequency = excluded.output_frequency,
                    is_active = 1,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (row[0], row[8], row[9], row[4]),
            )
            conn.exec_driver_sql(
                """
                INSERT OR IGNORE INTO market_data_collection_policies
                (item_type, item_code, frequency, initial_lookback_value, initial_lookback_unit, overlap_value, overlap_unit,
                 minimum_refresh_interval_hours, max_retry_count, timeout_seconds, is_auto_collect, is_active)
                VALUES ('INDICATOR', ?, ?, 5, 'YEARS',
                        CASE ? WHEN 'MONTHLY' THEN 6 ELSE 10 END,
                        CASE ? WHEN 'MONTHLY' THEN 'MONTHS' ELSE 'DAYS' END,
                        0, 1, 5, 1, 1)
                """,
                (row[0], row[4], row[4], row[4]),
            )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_objective_phenomena (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phenomenon_code TEXT NOT NULL UNIQUE,
                source_composite_signal_id INTEGER NOT NULL UNIQUE,
                source_rule_version INTEGER NOT NULL DEFAULT 1,
                source_title TEXT NOT NULL,
                display_title TEXT,
                category TEXT,
                tags_json TEXT NOT NULL DEFAULT '[]',
                description TEXT,
                operation_grade TEXT NOT NULL DEFAULT 'REFERENCE',
                current_state TEXT NOT NULL DEFAULT 'NOT_EVALUATED',
                phenomenon_score REAL,
                first_observed_at TEXT,
                confirmed_at TEXT,
                released_at TEXT,
                last_evaluated_at TEXT,
                evidence_count INTEGER NOT NULL DEFAULT 0,
                opposing_count INTEGER NOT NULL DEFAULT 0,
                missing_count INTEGER NOT NULL DEFAULT 0,
                next_check_count INTEGER NOT NULL DEFAULT 0,
                user_confirmed_title INTEGER NOT NULL DEFAULT 0,
                user_note TEXT,
                importance TEXT NOT NULL DEFAULT 'NORMAL',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_composite_signal_id) REFERENCES market_signal_definitions(id) ON DELETE RESTRICT
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_objective_phenomenon_evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phenomenon_id INTEGER NOT NULL,
                source_composite_evaluation_id INTEGER,
                evaluation_type TEXT NOT NULL DEFAULT 'PERIODIC',
                observation_date TEXT NOT NULL,
                is_live INTEGER NOT NULL DEFAULT 1,
                previous_state TEXT,
                current_state TEXT NOT NULL,
                phenomenon_score REAL NOT NULL DEFAULT 0,
                evidence_count INTEGER NOT NULL DEFAULT 0,
                opposing_count INTEGER NOT NULL DEFAULT 0,
                missing_count INTEGER NOT NULL DEFAULT 0,
                next_check_count INTEGER NOT NULL DEFAULT 0,
                easy_explanation TEXT,
                is_state_transition INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(phenomenon_id, source_composite_evaluation_id, evaluation_type),
                FOREIGN KEY (phenomenon_id) REFERENCES market_objective_phenomena(id) ON DELETE CASCADE,
                FOREIGN KEY (source_composite_evaluation_id) REFERENCES market_signal_evaluations(id) ON DELETE SET NULL
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS market_objective_phenomenon_flow_candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phenomenon_id INTEGER NOT NULL,
                source_evaluation_id INTEGER,
                candidate_title TEXT NOT NULL,
                category TEXT,
                status TEXT NOT NULL DEFAULT 'CANDIDATE',
                importance TEXT NOT NULL DEFAULT 'NORMAL',
                user_note TEXT,
                auto_update INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (phenomenon_id) REFERENCES market_objective_phenomena(id) ON DELETE CASCADE,
                FOREIGN KEY (source_evaluation_id) REFERENCES market_objective_phenomenon_evaluations(id) ON DELETE SET NULL
            )
            """
        )
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_objective_phenomena_grade_state ON market_objective_phenomena(operation_grade, current_state)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_objective_phenomenon_eval_date ON market_objective_phenomenon_evaluations(phenomenon_id, observation_date DESC)")
        conn.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS idx_objective_flow_candidate_active ON market_objective_phenomenon_flow_candidates(phenomenon_id) WHERE status IN ('CANDIDATE', 'LINKED')")
        conn.exec_driver_sql(
            """
            INSERT OR IGNORE INTO market_objective_phenomena
            (phenomenon_code, source_composite_signal_id, source_rule_version, source_title,
             display_title, category, description, operation_grade, current_state)
            SELECT 'PHENOMENON_' || signal_code, id, current_version, signal_name,
                   signal_name, category, description,
                   CASE status WHEN 'ACTIVE' THEN 'OFFICIAL' ELSE 'REFERENCE' END,
                   'NOT_EVALUATED'
            FROM market_signal_definitions
            WHERE signal_type = 'COMPOSITE'
            """
        )
        conn.exec_driver_sql(
            """
            UPDATE market_objective_phenomena
            SET source_rule_version = COALESCE((SELECT current_version FROM market_signal_definitions WHERE id = source_composite_signal_id), source_rule_version),
                operation_grade = CASE (SELECT status FROM market_signal_definitions WHERE id = source_composite_signal_id)
                    WHEN 'ACTIVE' THEN 'OFFICIAL' ELSE 'REFERENCE' END,
                updated_at = CURRENT_TIMESTAMP
            """
        )
