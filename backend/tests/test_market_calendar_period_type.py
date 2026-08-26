from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.schemas.market_calendar_schema import (
    MarketCalendarEventCreateRequest,
    MarketCalendarEventUpdateRequest,
)
from backend.app.services.market_calendar_service import MarketCalendarService


def _calendar_connection(*, with_period_type: bool = True) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    period_column = "period_type TEXT NOT NULL DEFAULT 'D' CHECK(period_type IN ('D', 'M'))," if with_period_type else ""
    connection.executescript(f"""
        PRAGMA foreign_keys=ON;
        CREATE TABLE market_themes (
            id INTEGER PRIMARY KEY, theme_name TEXT, theme_level TEXT,
            is_active INTEGER, parent_theme_id INTEGER
        );
        CREATE TABLE stocks (
            id INTEGER PRIMARY KEY, stock_code TEXT, stock_name TEXT, is_active INTEGER
        );
        CREATE TABLE market_calendar_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            {period_column}
            start_date TEXT NOT NULL, end_date TEXT NOT NULL, theme_id INTEGER,
            title TEXT NOT NULL, summary TEXT, news_url TEXT,
            event_type TEXT NOT NULL DEFAULT 'news', importance TEXT NOT NULL DEFAULT 'medium', memo TEXT,
            is_active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            FOREIGN KEY(theme_id) REFERENCES market_themes(id) ON DELETE SET NULL
        );
        CREATE TABLE market_calendar_event_stocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT, event_id INTEGER NOT NULL, stock_id INTEGER NOT NULL,
            stock_code TEXT, stock_name TEXT, created_at TEXT NOT NULL, UNIQUE(event_id, stock_id),
            FOREIGN KEY(event_id) REFERENCES market_calendar_events(id) ON DELETE CASCADE,
            FOREIGN KEY(stock_id) REFERENCES stocks(id) ON DELETE CASCADE
        );
    """)
    return connection


def test_period_type_migration_preserves_existing_daily_event() -> None:
    connection = _calendar_connection(with_period_type=False)
    connection.execute(
        """INSERT INTO market_calendar_events
           (id, start_date, end_date, theme_id, title, event_type, importance, is_active, created_at, updated_at)
           VALUES (7, '2026-08-26', '2026-08-26', NULL, '기존 일정', 'news', 'medium', 1, 'now', 'now')"""
    )
    connection.commit()
    connection.executescript(Path("backend/app/sql/migrations/044_market_calendar_period_type.sql").read_text(encoding="utf-8"))
    row = connection.execute("SELECT id, start_date, end_date, period_type FROM market_calendar_events").fetchone()
    assert row == (7, "2026-08-26", "2026-08-26", "D")
    connection.close()


def test_monthly_event_normalization_visibility_and_same_id_daily_confirmation() -> None:
    connection = _calendar_connection()
    engine = create_engine("sqlite://", creator=lambda: connection)
    with Session(engine) as session:
        service = MarketCalendarService(session)
        created = service.create_event(MarketCalendarEventCreateRequest(
            period_type="M",
            start_date="2026-07-18",
            end_date="2026-09-02",
            title="3분기 내 정책 발표",
        ))
        assert created.period_type == "M"
        assert created.start_date == "2026-07-01"
        assert created.end_date == "2026-09-30"
        assert [event.id for event in service.list_monthly(month="2026-08").events] == [created.id]
        assert service.list_daily("2026-08-01").events == []

        updated = service.update_event(created.id, MarketCalendarEventUpdateRequest(
            period_type="D",
            start_date="2026-09-18",
            end_date="2026-09-18",
            title="정책 발표일 확정",
        ))
        assert updated.id == created.id
        assert updated.period_type == "D"
        assert [event.id for event in service.list_daily("2026-09-18").events] == [created.id]
    engine.dispose()


def test_monthly_event_rejects_reversed_month_range() -> None:
    connection = _calendar_connection()
    engine = create_engine("sqlite://", creator=lambda: connection)
    with Session(engine) as session, pytest.raises(HTTPException) as error:
        MarketCalendarService(session).create_event(MarketCalendarEventCreateRequest(
            period_type="M",
            start_date="2026-09-01",
            end_date="2026-07-31",
            title="잘못된 기간",
        ))
    assert error.value.status_code == 400
    assert error.value.detail == "종료월은 시작월보다 빠를 수 없습니다."
    engine.dispose()
