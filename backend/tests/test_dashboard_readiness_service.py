from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.services.dashboard_readiness_service import DashboardReadinessService


def test_readiness_uses_aggregate_data_without_loading_detail_rows():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE market_themes (id INTEGER, is_active INTEGER, theme_level TEXT)"))
        connection.execute(text("CREATE TABLE market_theme_daily_returns (theme_id INTEGER, return_date TEXT, last_refreshed_at TEXT)"))
        connection.execute(text("CREATE TABLE market_theme_stocks (theme_id INTEGER, is_active INTEGER)"))
        connection.execute(text("CREATE TABLE collection_runs (id INTEGER, collector_name TEXT, status TEXT)"))
        connection.execute(text("CREATE TABLE market_indexes (index_code TEXT, is_active INTEGER)"))
        connection.execute(text("CREATE TABLE market_index_daily_prices (index_code TEXT, price_date TEXT)"))
        connection.execute(text("CREATE TABLE market_indicators (indicator_code TEXT, is_active INTEGER)"))
        connection.execute(text("CREATE TABLE market_indicator_values (indicator_code TEXT, value_date TEXT)"))
        connection.execute(text("CREATE TABLE market_data_collection_runs (id INTEGER, run_type TEXT, status TEXT, started_at TEXT, finished_at TEXT)"))
        connection.execute(text("INSERT INTO market_themes VALUES (1,1,'THEME'),(2,0,'THEME'),(3,1,'THEME_GROUP')"))
        connection.execute(text("INSERT INTO market_theme_daily_returns VALUES (1,'2026-09-15','2026-09-15 18:00:00'),(2,'2026-09-16','2026-09-16 18:00:00')"))
        connection.execute(text("INSERT INTO market_theme_stocks VALUES (1,1),(1,1),(2,1),(3,1)"))
        connection.execute(text("INSERT INTO collection_runs VALUES (1,'market_theme_price_flow_refresh','success')"))
        connection.execute(text("INSERT INTO market_indexes VALUES ('KOSPI',1),('OLD',0)"))
        connection.execute(text("INSERT INTO market_index_daily_prices VALUES ('KOSPI','2026-09-16'),('OLD','2026-09-17')"))
        connection.execute(text("INSERT INTO market_indicators VALUES ('USD',1),('OLD',0)"))
        connection.execute(text("INSERT INTO market_indicator_values VALUES ('USD','2026-09-15'),('OLD','2026-09-18')"))
        connection.execute(text("INSERT INTO market_data_collection_runs VALUES (1,'SELECTED','SUCCESS','2026-09-16 08:00:00',NULL),(2,'INCREMENTAL_ALL','SUCCESS','2026-09-15 23:00:00','2026-09-15 23:10:00')"))

    query_count = 0

    def count_query(*_args):
        nonlocal query_count
        query_count += 1

    event.listen(engine, "before_cursor_execute", count_query)
    with Session(engine) as session:
        result = DashboardReadinessService(session).get()

    assert query_count == 1
    assert result == {
        "theme": {
            "data_date": "2026-09-15",
            "last_success_at": "2026-09-15 18:00:00",
            "linked_stock_count": 2,
            "run_status": "success",
        },
        "market": {
            "data_date": "2026-09-16",
            "last_run_at": "2026-09-15 23:10:00",
            "active_indicator_count": 2,
            "run_status": "SUCCESS",
        },
    }
