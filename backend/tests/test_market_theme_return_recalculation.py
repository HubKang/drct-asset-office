from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.app.services.external_kiwoom_service import ExternalKiwoomService


def _create_schema(engine) -> None:  # type: ignore[no-untyped-def]
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE market_themes (id INTEGER PRIMARY KEY, theme_name TEXT, parent_theme_id INTEGER)"
        )
        conn.exec_driver_sql(
            "CREATE TABLE stocks (id INTEGER PRIMARY KEY, stock_code TEXT, stock_name TEXT, is_active INTEGER)"
        )
        conn.exec_driver_sql(
            """CREATE TABLE market_theme_stocks (
                theme_id INTEGER, stock_id INTEGER, is_active INTEGER, is_primary INTEGER
            )"""
        )
        conn.exec_driver_sql(
            """CREATE TABLE stock_daily_prices (
                stock_id INTEGER, trade_date TEXT, change_rate REAL,
                trading_value INTEGER, close_price REAL,
                UNIQUE(stock_id, trade_date)
            )"""
        )
        conn.exec_driver_sql(
            """CREATE TABLE market_theme_daily_returns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                theme_id INTEGER, return_date TEXT, avg_change_rate REAL,
                stock_count INTEGER, success_stock_count INTEGER, failed_stock_count INTEGER,
                rising_stock_count INTEGER, falling_stock_count INTEGER, flat_stock_count INTEGER,
                total_trading_value INTEGER, total_trading_value_100m REAL,
                data_source TEXT, first_created_at TEXT, last_refreshed_at TEXT,
                refresh_count INTEGER, created_at TEXT, updated_at TEXT,
                UNIQUE(theme_id, return_date)
            )"""
        )
        conn.exec_driver_sql(
            """CREATE TABLE market_theme_stock_daily_returns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                theme_daily_return_id INTEGER, theme_id INTEGER, stock_id INTEGER,
                stock_code TEXT, stock_name TEXT, return_date TEXT, change_rate REAL,
                trading_value INTEGER, trading_value_100m REAL, current_price INTEGER,
                data_status TEXT, error_message TEXT, created_at TEXT, updated_at TEXT,
                UNIQUE(theme_id, stock_id, return_date)
            )"""
        )


def test_recalculate_returns_uses_current_members_and_upserts_without_touching_other_theme(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    engine = create_engine("sqlite+pysqlite:///:memory:")
    _create_schema(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("INSERT INTO market_themes VALUES (1, '재구성 테마', NULL), (2, '다른 테마', NULL)")
        conn.exec_driver_sql(
            "INSERT INTO stocks VALUES (10, '000010', 'A', 1), (20, '000020', 'B', 1), (30, '000030', 'C', 1)"
        )
        conn.exec_driver_sql(
            "INSERT INTO market_theme_stocks VALUES (1, 10, 1, 1), (1, 20, 1, 0), (1, 30, 0, 0), (2, 30, 1, 1)"
        )
        conn.exec_driver_sql(
            """INSERT INTO stock_daily_prices VALUES
                (10, '2026-07-01', 10.0, 100, 1100),
                (20, '2026-07-01', -4.0, 200, 960),
                (30, '2026-07-01', 100.0, 300, 2000),
                (10, '2026-07-03', 5.0, 150, 1155)
            """
        )
        conn.exec_driver_sql(
            """INSERT INTO market_theme_daily_returns VALUES
                (1, 1, '2026-07-01', 99.0, 3, 3, 0, 3, 0, 0, 0, 0, 'old', 'x', 'x', 1, 'x', 'x'),
                (2, 1, '2026-07-02', 50.0, 3, 3, 0, 3, 0, 0, 0, 0, 'old', 'x', 'x', 1, 'x', 'x'),
                (3, 2, '2026-07-01', 7.7, 1, 1, 0, 1, 0, 0, 0, 0, 'old', 'x', 'x', 1, 'x', 'x')
            """
        )
        conn.exec_driver_sql(
            """INSERT INTO market_theme_stock_daily_returns VALUES
                (1, 1, 1, 10, '000010', 'A', '2026-07-01', 10.0, 100, 1, 1100, 'success', NULL, 'x', 'x'),
                (2, 1, 1, 30, '000030', 'C', '2026-07-01', 100.0, 300, 3, 2000, 'success', NULL, 'x', 'x')
            """
        )

    with Session(engine) as db:
        def forbid_external_provider() -> None:
            raise AssertionError("manual recalculation must not instantiate an external market-data provider")

        monkeypatch.setattr(
            "backend.app.services.external_kiwoom_service.KiwoomRestMarketIndicatorProvider",
            forbid_external_provider,
        )
        service = ExternalKiwoomService(db)
        preview = service.get_market_theme_return_recalculation_preview(1)
        assert preview.data_source == "STORED_STOCK_DAILY_PRICES"
        assert preview.connected_stock_count == 2
        assert preview.period_from == "2026-07-01"
        assert preview.period_to == "2026-07-03"

        result = service.recalculate_market_theme_returns(1)
        assert result.processed_date_count == 2
        assert result.updated_count == 1
        assert result.inserted_count == 1
        assert result.skipped_date_count == 1

        rows = db.execute(
            text(
                """SELECT return_date, avg_change_rate, stock_count, success_stock_count, failed_stock_count
                   FROM market_theme_daily_returns WHERE theme_id=1 ORDER BY return_date"""
            )
        ).mappings().all()
        assert [dict(row) for row in rows] == [
            {
                "return_date": "2026-07-01",
                "avg_change_rate": 3.0,
                "stock_count": 2,
                "success_stock_count": 2,
                "failed_stock_count": 0,
            },
            {
                "return_date": "2026-07-02",
                "avg_change_rate": None,
                "stock_count": 2,
                "success_stock_count": 0,
                "failed_stock_count": 2,
            },
            {
                "return_date": "2026-07-03",
                "avg_change_rate": 5.0,
                "stock_count": 2,
                "success_stock_count": 1,
                "failed_stock_count": 1,
            },
        ]

        stale_detail = db.execute(
            text(
                "SELECT data_status FROM market_theme_stock_daily_returns WHERE theme_id=1 AND stock_id=30"
            )
        ).scalar_one()
        assert stale_detail == "inactive"
        other_theme_rate = db.execute(
            text("SELECT avg_change_rate FROM market_theme_daily_returns WHERE theme_id=2")
        ).scalar_one()
        assert other_theme_rate == 7.7


def test_recalculate_summary_excludes_missing_members_instead_of_using_zero() -> None:
    summary = ExternalKiwoomService._summarize_theme_return_rows(
        [
            {"data_status": "success", "change_rate": 10.0, "trading_value": 100},
            {"data_status": "missing", "change_rate": None, "trading_value": None},
        ],
        connected_stock_count=2,
    )

    assert summary["avg_change_rate"] == 10.0
    assert summary["success_stock_count"] == 1
    assert summary["failed_stock_count"] == 1
