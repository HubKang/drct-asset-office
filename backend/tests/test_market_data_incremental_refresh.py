from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.services.market_data_collection_service import MarketDataCollectionService
from backend.app.services.market_index_service import MarketIndexService


def _session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    return Session(engine)


def test_incremental_all_retries_active_error_items() -> None:
    db = _session()
    db.execute(text("CREATE TABLE market_indexes (index_code TEXT, is_active INTEGER, collection_status TEXT)"))
    db.execute(text("CREATE TABLE market_indicators (indicator_code TEXT, is_active INTEGER, collection_status TEXT)"))
    db.execute(
        text(
            "INSERT INTO market_indexes VALUES "
            "('KOSPI', 1, 'ERROR'), ('CUSTOM', 1, 'CUSTOM_INDEX_REQUIRED'), ('OFF', 0, 'LATEST')"
        )
    )
    db.execute(
        text(
            "INSERT INTO market_indicators VALUES "
            "('US_CPI', 1, 'ERROR'), ('WAITING_DERIVED', 1, 'WAITING'), ('OFF', 0, 'LATEST')"
        )
    )

    targets = MarketDataCollectionService(db)._targets("INCREMENTAL_ALL", None)

    assert {tuple(item.values()) for item in targets} == {
        ("INDEX", "KOSPI"),
        ("INDICATOR", "US_CPI"),
        ("INDICATOR", "WAITING_DERIVED"),
    }


def test_collection_summary_counts_waiting_separately() -> None:
    totals = MarketDataCollectionService._summarize(
        [
            {"status": "LATEST", "unchanged_count": 7},
            {"status": "WAITING"},
            {"status": "ERROR"},
        ]
    )

    assert totals["success_count"] == 1
    assert totals["waiting_count"] == 1
    assert totals["failed_count"] == 1
    assert totals["unchanged_count"] == 7


def test_collection_run_timestamps_are_returned_as_explicit_utc() -> None:
    db = _session()
    db.execute(text("""
        CREATE TABLE market_data_collection_runs (
            id INTEGER PRIMARY KEY, run_type TEXT, status TEXT,
            started_at TEXT, finished_at TEXT, target_count INTEGER,
            success_count INTEGER, inserted_count INTEGER, updated_count INTEGER,
            unchanged_count INTEGER, skipped_count INTEGER, failed_count INTEGER,
            elapsed_ms INTEGER, triggered_by TEXT, error_summary TEXT
        )
    """))
    db.execute(text("""
        INSERT INTO market_data_collection_runs VALUES
        (56, 'INCREMENTAL_ALL', 'PARTIAL_SUCCESS', '2026-08-26 07:47:40', '2026-08-26 07:47:56',
         57, 54, 0, 0, 40, 0, 3, 16000, 'USER', NULL)
    """))

    item = MarketDataCollectionService(db).list_runs(limit=1)["items"][0]

    assert item["started_at"] == "2026-08-26T07:47:40Z"
    assert item["finished_at"] == "2026-08-26T07:47:56Z"


def test_same_date_market_index_value_is_updated_and_counted() -> None:
    db = _session()
    db.execute(
        text(
            """
            CREATE TABLE market_index_daily_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                index_code TEXT NOT NULL,
                price_date TEXT NOT NULL,
                open_price REAL,
                high_price REAL,
                low_price REAL,
                close_price REAL,
                volume REAL,
                trading_value REAL,
                change_rate REAL,
                source_provider TEXT,
                collected_at TEXT,
                revised_at TEXT,
                created_at TEXT,
                updated_at TEXT,
                UNIQUE(index_code, price_date)
            )
            """
        )
    )
    service = MarketIndexService(db)
    morning = {
        "price_date": "2026-07-29",
        "open_price": 3000.0,
        "high_price": 3020.0,
        "low_price": 2990.0,
        "close_price": 3010.0,
        "volume": 100.0,
        "trading_value": 1000.0,
        "change_rate": 0.3,
    }
    final = {**morning, "high_price": 3050.0, "close_price": 3040.0, "volume": 250.0}

    assert service._upsert_daily_rows("KOSPI", [morning], source_provider="KIWOOM_REST") == {
        "inserted_count": 1,
        "updated_count": 0,
        "unchanged_count": 0,
    }
    assert service._upsert_daily_rows("KOSPI", [final], source_provider="KIWOOM_REST") == {
        "inserted_count": 0,
        "updated_count": 1,
        "unchanged_count": 0,
    }
    assert service._upsert_daily_rows("KOSPI", [final], source_provider="KIWOOM_REST") == {
        "inserted_count": 0,
        "updated_count": 0,
        "unchanged_count": 1,
    }
    saved = db.execute(
        text("SELECT close_price, volume, revised_at FROM market_index_daily_prices WHERE index_code='KOSPI'")
    ).mappings().one()
    assert saved["close_price"] == 3040.0
    assert saved["volume"] == 250.0
    assert saved["revised_at"] is not None
