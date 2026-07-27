from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.entities.market_theme import MarketTheme
from backend.app.entities.market_theme_stock import MarketThemeStock
from backend.app.entities.stock import Stock
from backend.app.schemas.market_theme_stock_schema import MarketThemeStockCreateRequest
from backend.app.services.market_theme_stock_service import MarketThemeStockService


def _session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Stock.__table__.create(engine)
    MarketTheme.__table__.create(engine)
    MarketThemeStock.__table__.create(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE market_trend_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_date TEXT NOT NULL,
                stock_id INTEGER NOT NULL,
                stock_code TEXT,
                theme_id INTEGER,
                user_memo TEXT,
                detection_source TEXT,
                updated_at TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                deleted_at TEXT
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE market_trend_event_theme_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                market_theme_id INTEGER NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                deleted_at TEXT
            )
            """
        )
    return Session(engine)


def _add_event(db: Session, trade_date: str, stock_id: int, theme_id: int, *, active: int = 1, memo: str = "") -> None:
    result = db.execute(
        text(
            """
            INSERT INTO market_trend_events
                (trade_date, stock_id, stock_code, theme_id, user_memo, detection_source, updated_at, is_active)
            VALUES
                (:trade_date, :stock_id, NULL, :theme_id, :memo, 'kiwoom_condition', :trade_date, :active)
            """
        ),
        {"trade_date": trade_date, "stock_id": stock_id, "theme_id": theme_id, "active": active, "memo": memo},
    )
    db.execute(
        text(
            """
            INSERT INTO market_trend_event_theme_links (event_id, market_theme_id, is_active)
            VALUES (:event_id, :theme_id, 1)
            """
        ),
        {"event_id": int(result.lastrowid or 0), "theme_id": theme_id},
    )


def test_supply_summary_counts_distinct_dates_and_survives_reconnect() -> None:
    db = _session()
    now = "2026-07-20 10:00:00"
    theme = MarketTheme(
        theme_name="반도체",
        theme_code="TEST_SEMI",
        theme_type="theme",
        theme_level="THEME",
        description=None,
        keywords="[]",
        parent_theme_id=None,
        is_supply_theme=1,
        is_active=1,
        sort_order=1,
        created_at=now,
        updated_at=now,
    )
    other_theme = MarketTheme(
        theme_name="AI",
        theme_code="TEST_AI",
        theme_type="theme",
        theme_level="THEME",
        description=None,
        keywords="[]",
        parent_theme_id=None,
        is_supply_theme=1,
        is_active=1,
        sort_order=2,
        created_at=now,
        updated_at=now,
    )
    stock = Stock(stock_code="T00001", stock_name="테스트종목", market="KOSPI", is_active=1, created_at=now, updated_at=now)
    no_history_stock = Stock(stock_code="T00002", stock_name="이력없음", market="KOSDAQ", is_active=1, created_at=now, updated_at=now)
    db.add_all([theme, other_theme, stock, no_history_stock])
    db.flush()
    mapping = MarketThemeStock(
        theme_id=theme.id,
        stock_id=stock.id,
        mapping_source="manual",
        confidence_score=1.0,
        is_primary=1,
        is_active=1,
        created_at=now,
        updated_at=now,
    )
    empty_mapping = MarketThemeStock(
        theme_id=theme.id,
        stock_id=no_history_stock.id,
        mapping_source="manual",
        confidence_score=1.0,
        is_primary=0,
        is_active=1,
        created_at=now,
        updated_at=now,
    )
    db.add_all([mapping, empty_mapping])
    db.flush()

    _add_event(db, "2026-06-01", stock.id, theme.id, memo="반도체 최초 메모")
    _add_event(db, "2026-06-21", stock.id, theme.id, memo="반도체 메모")
    _add_event(db, "2026-07-20", stock.id, theme.id)
    _add_event(db, "2026-07-20", stock.id, theme.id)
    _add_event(db, "2026-07-20", stock.id, other_theme.id)
    _add_event(db, "2026-07-01", stock.id, other_theme.id, memo="AI 메모")
    _add_event(db, "2026-07-10", stock.id, theme.id, active=0)
    db.commit()

    service = MarketThemeStockService(db)
    rows = service.list_theme_stocks(theme.id, as_of_date=date(2026, 7, 20))
    counted = next(row for row in rows if row.stock_id == stock.id)
    empty = next(row for row in rows if row.stock_id == no_history_stock.id)
    assert counted.supply_day_count == 3
    assert counted.recent_30d_supply_day_count == 2
    assert counted.first_supply_date == "2026-06-01"
    assert counted.last_supply_date == "2026-07-20"
    assert empty.supply_day_count == 0
    assert empty.first_supply_date is None
    empty_summary = service.get_supply_summary(theme.id, no_history_stock.id, as_of_date=date(2026, 7, 20))
    assert empty_summary.supply_day_count == 0
    assert empty_summary.recent_supply_dates == []

    summary = service.get_supply_summary(theme.id, stock.id, as_of_date=date(2026, 7, 20))
    assert summary.supply_day_count == 3
    assert summary.recent_30d_supply_day_count == 2
    assert summary.all_theme_supply_day_count == 4
    assert summary.recent_supply_dates == ["2026-07-20", "2026-06-21", "2026-06-01"]

    service.deactivate_theme_stock(mapping.id)
    disconnected = service.get_supply_summary(theme.id, stock.id, as_of_date=date(2026, 7, 20))
    assert disconnected.supply_day_count == 3

    service.create_theme_stock(theme.id, MarketThemeStockCreateRequest(stock_id=stock.id, is_primary=True))
    reconnected = service.list_theme_stocks(theme.id, as_of_date=date(2026, 7, 20))
    assert next(row for row in reconnected if row.stock_id == stock.id).supply_day_count == 3


    assert summary.current_theme.theme_id == theme.id
    assert summary.current_theme_supply_count == 3
    assert summary.overall_stock_supply_count == 4
    assert summary.current_theme_supply_dates == ["2026-07-20", "2026-06-21", "2026-06-01"]
    assert [(item.theme_id, item.supply_count) for item in summary.linked_theme_supply_summaries] == [
        (theme.id, 3),
    ]
    assert all(item.is_current_theme_supply_date for item in summary.stock_memos if item.detected_date in {"2026-06-01", "2026-06-21"})

    other_mapping = MarketThemeStock(
        theme_id=other_theme.id,
        stock_id=stock.id,
        mapping_source="manual",
        confidence_score=1.0,
        is_primary=0,
        is_active=1,
        created_at=now,
        updated_at=now,
    )
    db.add(other_mapping)
    db.commit()
    other_summary = service.get_supply_summary(other_theme.id, stock.id, as_of_date=date(2026, 7, 20))
    assert other_summary.current_theme_supply_count == 2
    assert other_summary.current_theme_supply_dates == ["2026-07-20", "2026-07-01"]
    assert other_summary.overall_stock_supply_count == 4
    assert [(item.theme_id, item.supply_count, item.is_current_theme) for item in other_summary.linked_theme_supply_summaries] == [
        (other_theme.id, 2, True),
        (theme.id, 3, False),
    ]
    ai_memo = next(item for item in other_summary.stock_memos if item.detected_date == "2026-07-01")
    semiconductor_memo = next(item for item in other_summary.stock_memos if item.detected_date == "2026-06-21")
    assert ai_memo.is_current_theme_supply_date is True
    assert semiconductor_memo.is_current_theme_supply_date is False
    db.close()
