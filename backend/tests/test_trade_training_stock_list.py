from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.services.trade_training_service import TradeTrainingService


def _session(stock_count: int = 17) -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE stocks (id INTEGER PRIMARY KEY, stock_code TEXT, stock_name TEXT, market TEXT)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE stock_daily_prices (stock_id INTEGER, trade_date TEXT, source TEXT)"
        )
        for stock_id in range(1, stock_count + 1):
            connection.exec_driver_sql(
                "INSERT INTO stocks VALUES (?, ?, ?, ?)",
                (stock_id, f"{stock_id:06d}", f"Stock {stock_id:02d}", "KOSPI"),
            )
            connection.exec_driver_sql(
                "INSERT INTO stock_daily_prices VALUES (?, ?, ?)",
                (stock_id, "2026-07-01", "kiwoom_rest"),
            )
            connection.exec_driver_sql(
                "INSERT INTO stock_daily_prices VALUES (?, ?, ?)",
                (stock_id, "2026-08-07", "kiwoom_rest"),
            )
        connection.exec_driver_sql(
            "INSERT INTO stock_daily_prices VALUES (1, '2026-08-07', 'pykrx')"
        )
        connection.exec_driver_sql(
            "INSERT INTO stocks VALUES (999, '999999', 'No Price', 'KOSPI')"
        )
    return Session(engine)


def test_training_stock_list_paginates_every_distinct_priced_stock() -> None:
    db = _session()
    try:
        service = TradeTrainingService(db)
        first = service.list_stocks(q=None, page=1, page_size=8)
        second = service.list_stocks(q=None, page=2, page_size=8)
        last = service.list_stocks(q=None, page=3, page_size=8)
    finally:
        db.close()

    assert first["total_count"] == 17
    assert first["total_pages"] == 3
    assert len(first["items"]) == 8
    assert len(second["items"]) == 8
    assert len(last["items"]) == 1
    stock_ids = [item["stock_id"] for page in (first, second, last) for item in page["items"]]
    assert len(stock_ids) == len(set(stock_ids)) == 17
    assert first["items"][0]["price_count"] == 2
    assert first["items"][0]["first_date"] == "2026-07-01"
    assert first["items"][0]["last_date"] == "2026-08-07"


def test_training_stock_search_uses_the_same_priced_stock_population() -> None:
    db = _session()
    try:
        service = TradeTrainingService(db)
        by_name = service.list_stocks(q="Stock 17", page=1, page_size=8)
        by_code = service.list_stocks(q="000017", page=1, page_size=8)
        without_prices = service.list_stocks(q="No Price", page=1, page_size=8)
    finally:
        db.close()

    assert by_name["total_count"] == 1
    assert by_name["items"][0]["stock_id"] == 17
    assert by_code["total_count"] == 1
    assert by_code["items"][0]["stock_id"] == 17
    assert without_prices["total_count"] == 0
    assert without_prices["items"] == []
