from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.entities.market_theme import MarketTheme
from backend.app.services.market_theme_service import MarketThemeService


RELATED_THEME_COLUMNS = {
    "market_theme_stock_daily_returns": "theme_id INTEGER",
    "market_theme_daily_returns": "theme_id INTEGER",
    "market_theme_realtime_returns": "theme_id INTEGER",
    "market_theme_return_prediction_items": "theme_id INTEGER",
    "market_theme_observation_items": "theme_id INTEGER",
    "market_theme_observation_validation_samples": "theme_id INTEGER",
    "market_calendar_events": "theme_id INTEGER",
    "daily_theme_flow_ranks": "market_theme_id INTEGER",
    "briefing_theme_links": "market_theme_id INTEGER",
    "market_trend_event_theme_links": "market_theme_id INTEGER",
    "market_theme_stock_candidates": "theme_id INTEGER",
    "market_theme_stocks": "theme_id INTEGER",
}


def _seed() -> tuple[Session, MarketTheme, MarketTheme]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    MarketTheme.__table__.create(engine)
    with engine.begin() as connection:
        for table_name, column_definition in RELATED_THEME_COLUMNS.items():
            connection.execute(text(f"CREATE TABLE {table_name} (id INTEGER PRIMARY KEY, {column_definition})"))
        connection.execute(text("CREATE TABLE market_trend_events (id INTEGER PRIMARY KEY, theme_id INTEGER, primary_theme_id INTEGER)"))
        connection.execute(text("CREATE TABLE market_index_theme_mappings (id INTEGER PRIMARY KEY, theme_id INTEGER, theme_group_id INTEGER)"))

    db = Session(engine)
    now = "2026-08-13 16:00:00"
    group = MarketTheme(
        theme_name="unused group", theme_code="unused-group", theme_type="theme",
        theme_level="THEME_GROUP", keywords="[]", is_supply_theme=0, is_active=0,
        sort_order=1, created_at=now, updated_at=now,
    )
    db.add(group)
    db.flush()
    child = MarketTheme(
        theme_name="unused child", theme_code="unused-child", theme_type="theme",
        theme_level="THEME", keywords="[]", parent_theme_id=group.id,
        is_supply_theme=0, is_active=0, sort_order=1, created_at=now, updated_at=now,
    )
    db.add(child)
    db.commit()
    return db, group, child


def test_delete_rejects_active_theme() -> None:
    db, _, child = _seed()
    child.is_active = 1
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        MarketThemeService(db).delete_theme(child.id)

    assert exc_info.value.status_code == 409
    assert db.get(MarketTheme, child.id) is not None


def test_delete_inactive_group_removes_children_and_related_rows() -> None:
    db, group, child = _seed()
    db.execute(text("INSERT INTO market_theme_stocks (theme_id) VALUES (:id)"), {"id": child.id})
    db.execute(text("INSERT INTO market_theme_daily_returns (theme_id) VALUES (:id)"), {"id": child.id})
    db.execute(text("INSERT INTO market_trend_events (theme_id, primary_theme_id) VALUES (:id, :id)"), {"id": child.id})
    db.commit()

    result = MarketThemeService(db).delete_theme(group.id)

    assert result.deleted_theme_count == 2
    assert result.deleted_related_row_count == 2
    assert result.detached_event_reference_count == 2
    assert db.get(MarketTheme, group.id) is None
    assert db.get(MarketTheme, child.id) is None
    assert db.execute(text("SELECT count(*) FROM market_theme_stocks")).scalar_one() == 0
    event = db.execute(text("SELECT theme_id, primary_theme_id FROM market_trend_events")).one()
    assert event == (None, None)


def test_delete_group_rejects_active_child() -> None:
    db, group, child = _seed()
    child.is_active = 1
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        MarketThemeService(db).delete_theme(group.id)

    assert exc_info.value.status_code == 409
    assert db.get(MarketTheme, group.id) is not None
    assert db.get(MarketTheme, child.id) is not None
