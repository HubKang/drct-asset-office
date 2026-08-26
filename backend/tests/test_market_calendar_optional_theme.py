from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.app.schemas.market_calendar_schema import MarketCalendarEventCreateRequest
from backend.app.services.market_calendar_service import MarketCalendarService


def test_optional_theme_migration_preserves_events_and_allows_unassigned_news() -> None:
    connection = sqlite3.connect(":memory:")
    connection.executescript("""
        PRAGMA foreign_keys=ON;
        CREATE TABLE market_themes (id INTEGER PRIMARY KEY, theme_name TEXT, theme_level TEXT, is_active INTEGER, parent_theme_id INTEGER);
        CREATE TABLE stocks (id INTEGER PRIMARY KEY, stock_code TEXT, stock_name TEXT, is_active INTEGER);
        CREATE TABLE market_calendar_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, start_date TEXT NOT NULL, end_date TEXT NOT NULL,
            theme_id INTEGER NOT NULL, title TEXT NOT NULL, summary TEXT, news_url TEXT,
            event_type TEXT NOT NULL DEFAULT 'news', importance TEXT NOT NULL DEFAULT 'medium', memo TEXT,
            is_active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            FOREIGN KEY(theme_id) REFERENCES market_themes(id) ON DELETE CASCADE
        );
        CREATE TABLE market_calendar_event_stocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL, stock_id INTEGER NOT NULL,
            stock_code TEXT, stock_name TEXT, created_at TEXT NOT NULL, UNIQUE(event_id, stock_id),
            FOREIGN KEY(event_id) REFERENCES market_calendar_events(id) ON DELETE CASCADE,
            FOREIGN KEY(stock_id) REFERENCES stocks(id) ON DELETE CASCADE
        );
        INSERT INTO market_themes VALUES (1, 'AI', 'THEME', 1, NULL);
        INSERT INTO stocks VALUES (1, '000001', '테스트', 1);
        INSERT INTO market_calendar_events VALUES (1, '2026-08-26', '2026-08-26', 1, '기존 뉴스', NULL, NULL, 'news', 'medium', NULL, 1, 'now', 'now');
        INSERT INTO market_calendar_event_stocks VALUES (1, 1, 1, '000001', '테스트', 'now');
    """)
    migration = Path("backend/app/sql/migrations/043_market_calendar_optional_theme.sql").read_text(encoding="utf-8")
    connection.executescript(migration)
    connection.executescript(Path("backend/app/sql/migrations/044_market_calendar_period_type.sql").read_text(encoding="utf-8"))
    theme_column = next(row for row in connection.execute("PRAGMA table_info(market_calendar_events)") if row[1] == "theme_id")
    assert theme_column[3] == 0
    assert connection.execute("SELECT COUNT(*) FROM market_calendar_events").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM market_calendar_event_stocks").fetchone()[0] == 1
    engine = create_engine("sqlite://", creator=lambda: connection)
    with Session(engine) as session:
        created = MarketCalendarService(session).create_event(MarketCalendarEventCreateRequest(
            start_date="2026-08-27", end_date="2026-08-27", theme_id=None,
            title="테마 없는 뉴스", event_type="news", importance="medium",
        ))
        assert created.theme_id is None
        assert created.theme_name is None
        assert session.scalar(text("SELECT COUNT(*) FROM market_calendar_events WHERE theme_id IS NULL")) == 1
    engine.dispose()
