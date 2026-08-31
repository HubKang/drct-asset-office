from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.app.services.stock_tracking_service import StockTrackingService


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    db = Session(engine)
    db.execute(text("""
        CREATE TABLE stock_tracking_groups (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            success_rule_note TEXT,
            fail_rule_note TEXT,
            observation_note TEXT,
            is_active INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """))
    db.execute(text("""
        CREATE TABLE stock_tracking_items (
            id INTEGER PRIMARY KEY,
            group_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            price_status TEXT,
            tracking_base_date TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """))
    db.execute(text("""
        CREATE TABLE price_collection_targets (
            source_type TEXT NOT NULL,
            source_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            end_date TEXT,
            error_message TEXT,
            updated_at TEXT NOT NULL
        )
    """))
    db.execute(text("""
        INSERT INTO stock_tracking_groups
            (id, name, is_active, created_at, updated_at)
        VALUES
            (1, '테스트 그룹', 1, '2026-08-31 09:00:00', '2026-08-31 09:00:00'),
            (2, '다른 활성 그룹', 1, '2026-08-31 09:00:00', '2026-08-31 09:00:00')
    """))
    db.execute(text("""
        INSERT INTO stock_tracking_items
            (id, group_id, status, price_status, tracking_base_date, updated_at)
        VALUES
            (11, 1, 'TRACKING', 'LATEST', '2026-08-28', '2026-08-31 09:00:00'),
            (12, 1, 'HOLD', 'ERROR', '2026-08-27', '2026-08-31 09:00:00'),
            (13, 1, 'SUCCESS', 'STOPPED', '2026-08-26', '2026-08-31 09:00:00'),
            (21, 2, 'TRACKING', 'LATEST', '2026-08-29', '2026-08-31 09:00:00')
    """))
    db.execute(text("""
        INSERT INTO price_collection_targets
            (source_type, source_id, status, end_date, error_message, updated_at)
        VALUES
            ('STOCK_TRACKING', 11, 'ACTIVE', NULL, NULL, '2026-08-31 09:00:00'),
            ('STOCK_TRACKING', 12, 'ERROR', NULL, 'temporary', '2026-08-31 09:00:00'),
            ('STOCK_TRACKING', 13, 'STOPPED', '2026-08-30', NULL, '2026-08-31 09:00:00'),
            ('STOCK_TRACKING', 21, 'ACTIVE', NULL, NULL, '2026-08-31 09:00:00')
    """))
    db.commit()
    return db


def target_states(db: Session) -> dict[int, tuple[str, str | None, str | None]]:
    rows = db.execute(text("""
        SELECT source_id, status, end_date, error_message
        FROM price_collection_targets
        ORDER BY source_id
    """)).mappings().all()
    return {
        int(row["source_id"]): (str(row["status"]), row["end_date"], row["error_message"])
        for row in rows
    }


def test_group_deactivation_pauses_collection_without_deleting_history() -> None:
    db = make_session()
    service = StockTrackingService(db)

    group = service.set_group_active(1, False)

    assert group.is_active == 0
    assert group.item_count == 3
    assert target_states(db) == {
        11: ("PAUSED", None, None),
        12: ("PAUSED", None, "temporary"),
        13: ("STOPPED", "2026-08-30", None),
        21: ("ACTIVE", None, None),
    }
    assert service._list_collectable_tracking_item_ids() == [21]


def test_group_reactivation_resumes_only_non_finalized_items() -> None:
    db = make_session()
    service = StockTrackingService(db)
    service.set_group_active(1, False)

    group = service.set_group_active(1, True)

    assert group.is_active == 1
    assert target_states(db) == {
        11: ("ACTIVE", None, None),
        12: ("ACTIVE", None, None),
        13: ("STOPPED", "2026-08-30", None),
        21: ("ACTIVE", None, None),
    }
    assert service._list_collectable_tracking_item_ids() == [21, 11, 12]
