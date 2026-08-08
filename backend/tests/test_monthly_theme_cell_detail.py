from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.services.external_kiwoom_service import ExternalKiwoomService
from backend.app.services.monthly_theme_cell_detail_service import MonthlyThemeCellDetailService


def _session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE market_themes (id INTEGER PRIMARY KEY, theme_name TEXT, theme_level TEXT, parent_theme_id INTEGER)")
        conn.exec_driver_sql("CREATE TABLE stocks (id INTEGER PRIMARY KEY, stock_code TEXT, stock_name TEXT)")
        conn.exec_driver_sql("CREATE TABLE market_theme_stocks (theme_id INTEGER, stock_id INTEGER, is_active INTEGER, stock_memo TEXT)")
        conn.exec_driver_sql("""CREATE TABLE market_trend_events (
            id INTEGER PRIMARY KEY, trade_date TEXT, stock_id INTEGER, stock_code TEXT, stock_name TEXT,
            change_rate REAL, trading_value INTEGER, theme_id INTEGER, detection_source TEXT,
            is_active INTEGER, deleted_at TEXT
        )""")
        conn.exec_driver_sql("CREATE TABLE market_trend_event_theme_links (event_id INTEGER, market_theme_id INTEGER)")
        conn.exec_driver_sql("""CREATE TABLE stock_daily_prices (
            stock_id INTEGER, trade_date TEXT, close_price REAL, change_rate REAL, trading_value INTEGER
        )""")
        conn.exec_driver_sql("""CREATE TABLE stock_investor_flows (
            stock_id INTEGER, flow_date TEXT, individual_net_amount INTEGER, foreign_net_amount INTEGER,
            institution_net_amount INTEGER, program_net_amount INTEGER
        )""")
        conn.exec_driver_sql("INSERT INTO market_themes VALUES (1, '반도체', 'THEME_GROUP', NULL)")
        conn.exec_driver_sql("INSERT INTO market_themes VALUES (12, 'AI반도체/HBM', 'THEME', 1)")
        conn.exec_driver_sql("INSERT INTO stocks VALUES (101, '000001', '첫째종목')")
        conn.exec_driver_sql("INSERT INTO stocks VALUES (102, '000002', '둘째종목')")
        conn.exec_driver_sql("INSERT INTO market_theme_stocks VALUES (12, 101, 1, 'HBM 검사')")
        conn.exec_driver_sql("INSERT INTO market_theme_stocks VALUES (12, 102, 0, 'AI 서버')")
        conn.exec_driver_sql("INSERT INTO market_trend_events VALUES (1, '2026-08-03', 101, '000001', '첫째종목', 12.0, 20000000000, NULL, 'kiwoom_condition', 1, NULL)")
        conn.exec_driver_sql("INSERT INTO market_trend_events VALUES (2, '2026-08-03', 102, '000002', '둘째종목', -2.0, 10000000000, NULL, 'kiwoom_condition', 1, NULL)")
        conn.exec_driver_sql("INSERT INTO market_trend_events VALUES (3, '2026-07-15', 101, '000001', '첫째종목', 3.0, 10000000000, NULL, 'kiwoom_condition', 1, NULL)")
        conn.exec_driver_sql("INSERT INTO market_trend_event_theme_links VALUES (1, 12)")
        conn.exec_driver_sql("INSERT INTO market_trend_event_theme_links VALUES (2, 12)")
        conn.exec_driver_sql("INSERT INTO market_trend_event_theme_links VALUES (3, 12)")
        conn.exec_driver_sql("INSERT INTO stock_daily_prices VALUES (101, '2026-08-03', 12000, 12.0, 20000000000)")
        conn.exec_driver_sql("INSERT INTO stock_daily_prices VALUES (102, '2026-08-03', 9800, -2.0, 10000000000)")
        conn.exec_driver_sql("INSERT INTO stock_investor_flows VALUES (101, '2026-08-03', -1000000000, 200000000, 900000000, 100000000)")
    return Session(engine)


def test_monthly_theme_cell_detail_uses_saved_event_stocks_and_selected_date_flow(monkeypatch) -> None:
    records = [
        {"trade_date": "2026-07-15", "market_theme_id": 12, "stock_id": 101, "stock_code": "000001", "stock_name": "첫째종목", "change_rate": 3.0, "trading_value": 10000000000},
        {"trade_date": "2026-08-03", "market_theme_id": 12, "stock_id": 101, "stock_code": "000001", "stock_name": "첫째종목", "change_rate": 12.0, "trading_value": 20000000000},
        {"trade_date": "2026-08-03", "market_theme_id": 12, "stock_id": 102, "stock_code": "000002", "stock_name": "둘째종목", "change_rate": -2.0, "trading_value": 10000000000},
    ]
    monkeypatch.setattr(
        ExternalKiwoomService,
        "_build_supply_theme_aggregation",
        lambda self, start, end: {"records": records, "diagnostics": None},
    )
    db = _session()
    try:
        detail = MonthlyThemeCellDetailService(db).get_detail(
            theme_id=12,
            event_date="2026-08-03",
            period_from="2026-07-03",
            period_to="2026-08-03",
        )
    finally:
        db.close()

    assert detail.theme.name == "AI반도체/HBM"
    assert detail.theme.group_name == "반도체"
    assert detail.summary.appearance_days == 2
    assert detail.summary.unique_stock_count == 2
    assert detail.summary.selected_stock_count == 2
    assert detail.summary.selected_avg_change_rate == 5.0
    assert detail.summary.selected_trading_value_100m == 300.0
    assert detail.summary.rise_count == 1
    assert detail.summary.fall_count == 1
    assert detail.summary.flow_ready_count == 1
    assert detail.summary.recent_appearance_dates == ["2026-07-15", "2026-08-03"]
    assert [stock.stock_code for stock in detail.stocks] == ["000002", "000001"]
    assert [stock.stock_memo for stock in detail.stocks] == ["AI 서버", "HBM 검사"]
    assert detail.stocks[0].flow_summary is None
    assert detail.stocks[1].flow_summary is not None
    assert detail.stocks[1].flow_summary.individual_net_amount == -1_000_000_000


def test_monthly_theme_cell_detail_returns_every_appearance_date(monkeypatch) -> None:
    appearance_dates = [
        "2026-07-10",
        "2026-07-14",
        "2026-07-15",
        "2026-07-16",
        "2026-07-20",
        "2026-07-21",
        "2026-07-23",
        "2026-07-31",
        "2026-08-03",
        "2026-08-04",
        "2026-08-06",
    ]
    records = [
        {
            "trade_date": trade_date,
            "market_theme_id": 12,
            "stock_id": 101,
            "stock_code": "000001",
            "stock_name": "첫째종목",
            "change_rate": 1.0,
            "trading_value": 10_000_000_000,
        }
        for trade_date in appearance_dates
    ]
    monkeypatch.setattr(
        ExternalKiwoomService,
        "_build_supply_theme_aggregation",
        lambda self, start, end: {"records": records, "diagnostics": None},
    )
    monkeypatch.setattr(
        MonthlyThemeCellDetailService,
        "_load_historical_event_stocks",
        lambda self, **kwargs: records,
    )
    db = _session()
    try:
        detail = MonthlyThemeCellDetailService(db).get_detail(
            theme_id=12,
            event_date="2026-08-06",
            period_from="2026-07-08",
            period_to="2026-08-08",
        )
    finally:
        db.close()

    assert detail.summary.appearance_days == 11
    assert detail.summary.recent_appearance_dates == appearance_dates


def test_selected_cell_uses_the_events_that_contributed_to_current_heatmap_classification(monkeypatch) -> None:
    selected_record = {
        "trade_date": "2026-07-22",
        "market_theme_id": 12,
        "stock_id": 101,
        "stock_code": "000001",
        "stock_name": "GS건설",
        "change_rate": 13.67,
        "trading_value": 102_828_167_400,
    }
    historical_record = {
        **selected_record,
        "trade_date": "2026-07-23",
        "change_rate": 2.0,
    }
    monkeypatch.setattr(
        ExternalKiwoomService,
        "_build_supply_theme_aggregation",
        lambda self, start, end: {"records": [selected_record], "diagnostics": None},
    )
    monkeypatch.setattr(
        MonthlyThemeCellDetailService,
        "_load_historical_event_stocks",
        lambda self, **kwargs: [historical_record],
    )
    db = _session()
    try:
        detail = MonthlyThemeCellDetailService(db).get_detail(
            theme_id=12,
            event_date="2026-07-22",
            period_from="2026-07-08",
            period_to="2026-08-08",
        )
    finally:
        db.close()

    assert detail.summary.selected_stock_count == 1
    assert detail.summary.selected_avg_change_rate == 13.67
    assert detail.summary.selected_trading_value_100m == 1028.2817
    assert detail.summary.recent_appearance_dates == ["2026-07-23"]
    assert [(stock.stock_code, stock.change_rate) for stock in detail.stocks] == [("000001", 13.67)]
