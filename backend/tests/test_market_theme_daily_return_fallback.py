from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.services.external_kiwoom_service import ExternalKiwoomService


def test_daily_return_falls_back_to_saved_price_and_flow_when_theme_snapshot_is_missing() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE market_themes (id INTEGER PRIMARY KEY, theme_name TEXT, parent_theme_id INTEGER)")
        conn.exec_driver_sql("CREATE TABLE stocks (id INTEGER PRIMARY KEY, stock_code TEXT, stock_name TEXT, is_active INTEGER)")
        conn.exec_driver_sql("CREATE TABLE market_theme_stocks (theme_id INTEGER, stock_id INTEGER, is_active INTEGER, is_primary INTEGER, stock_memo TEXT)")
        conn.exec_driver_sql("""CREATE TABLE market_theme_daily_returns (
            id INTEGER PRIMARY KEY, theme_id INTEGER, return_date TEXT, avg_change_rate REAL,
            stock_count INTEGER, success_stock_count INTEGER, failed_stock_count INTEGER,
            rising_stock_count INTEGER, falling_stock_count INTEGER, flat_stock_count INTEGER,
            total_trading_value_100m REAL, last_refreshed_at TEXT
        )""")
        conn.exec_driver_sql("""CREATE TABLE market_theme_stock_daily_returns (
            id INTEGER PRIMARY KEY, theme_daily_return_id INTEGER, theme_id INTEGER, stock_id INTEGER,
            return_date TEXT, trading_value INTEGER
        )""")
        conn.exec_driver_sql("""CREATE TABLE stock_daily_prices (
            stock_id INTEGER, trade_date TEXT, trading_value INTEGER, change_rate REAL, close_price REAL
        )""")
        conn.exec_driver_sql("""CREATE TABLE stock_investor_flows (
            stock_id INTEGER, flow_date TEXT, individual_net_amount INTEGER, foreign_net_amount INTEGER,
            institution_net_amount INTEGER, program_net_amount INTEGER
        )""")
        conn.exec_driver_sql("INSERT INTO market_themes VALUES (1, '테스트 테마', NULL)")
        conn.exec_driver_sql("INSERT INTO stocks VALUES (10, '000010', '테스트 종목', 1)")
        conn.exec_driver_sql("INSERT INTO market_theme_stocks VALUES (1, 10, 1, 1, '변압기')")
        conn.exec_driver_sql("INSERT INTO stock_daily_prices VALUES (10, '2026-07-01', 12300, 2.5, 1500)")
        conn.exec_driver_sql("INSERT INTO stock_investor_flows VALUES (10, '2026-07-01', -10, 20, 30, 5)")

    with Session(engine) as db:
        result = ExternalKiwoomService(db).get_market_theme_daily_return(1, "2026-07-01")

    assert result.return_date == "2026-07-01"
    assert result.stock_count == 1
    assert result.success_stock_count == 1
    assert result.avg_change_rate == 2.5
    assert result.total_trading_value_100m == 123.0
    assert result.stocks[0].stock_name == "테스트 종목"
    assert result.stocks[0].stock_memo == "변압기"
    assert result.stocks[0].flow_summary.foreign_net_amount == 20
    assert result.flow_summary.connected_stock_count == 1


def test_latest_return_lists_linked_stocks_before_first_return_refresh() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE market_themes (id INTEGER PRIMARY KEY, theme_name TEXT, parent_theme_id INTEGER)")
        conn.exec_driver_sql("CREATE TABLE stocks (id INTEGER PRIMARY KEY, stock_code TEXT, stock_name TEXT, is_active INTEGER)")
        conn.exec_driver_sql("CREATE TABLE market_theme_stocks (theme_id INTEGER, stock_id INTEGER, is_active INTEGER, is_primary INTEGER, stock_memo TEXT)")
        conn.exec_driver_sql("""CREATE TABLE market_theme_daily_returns (
            id INTEGER PRIMARY KEY, theme_id INTEGER, return_date TEXT, avg_change_rate REAL,
            stock_count INTEGER, success_stock_count INTEGER, failed_stock_count INTEGER,
            rising_stock_count INTEGER, falling_stock_count INTEGER, flat_stock_count INTEGER,
            total_trading_value_100m REAL, last_refreshed_at TEXT
        )""")
        conn.exec_driver_sql("INSERT INTO market_themes VALUES (1, 'Dr.CT Top10', NULL)")
        conn.exec_driver_sql("INSERT INTO stocks VALUES (10, '010120', 'LS ELECTRIC', 1), (20, '096770', 'SK이노베이션', 1)")
        conn.exec_driver_sql("INSERT INTO market_theme_stocks VALUES (1, 10, 1, 1, '전력기기'), (1, 20, 1, 0, '정유·ESS')")

    with Session(engine) as db:
        result = ExternalKiwoomService(db).get_market_theme_latest_return(1)

    assert result.return_date is None
    assert result.stock_count == 2
    assert [stock.stock_name for stock in result.stocks] == ["LS ELECTRIC", "SK이노베이션"]
    assert result.stocks[0].stock_memo == "전력기기"
    assert all(stock.data_status == "missing" for stock in result.stocks)
