from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.app.providers.market_data.kiwoom_rest_condition_provider import KiwoomRestConditionProvider
from backend.app.schemas.external_kiwoom_schema import KiwoomMarketEventSaveRequest
from backend.app.services.external_kiwoom_service import ExternalKiwoomService


def test_kiwoom_condition_change_rate_hundredths_are_percent_points() -> None:
    assert ExternalKiwoomService._normalize_change_rate(981) == 9.81
    assert ExternalKiwoomService._normalize_change_rate("-1234") == -12.34


def test_kiwoom_condition_change_rate_percent_values_are_kept() -> None:
    assert ExternalKiwoomService._normalize_change_rate(8.85) == 8.85
    assert ExternalKiwoomService._normalize_change_rate("0.85") == 0.85


def test_condition_provider_normalizes_integer_encoded_realtime_rates() -> None:
    provider = object.__new__(KiwoomRestConditionProvider)
    items, _, _ = provider._normalize_condition_results(
        {
            "data": [
                {"9001": "A007340", "302": "DN오토모티브", "10": "+000047500", "12": "+000000064", "13": "64417"},
                {"9001": "A446540", "302": "메가터치", "10": "+000006940", "flu_rt": "1.31", "13": "81843"},
            ]
        },
        condition_seq="3",
        condition_name="03. 이평조정_5,10,20,60",
    )

    assert items[0]["change_rate"] == 0.64
    assert items[1]["change_rate"] == 1.31


def test_condition_provider_keeps_zero_rate_instead_of_falling_through() -> None:
    assert KiwoomRestConditionProvider._get_condition_rate({"flu_rt": "0", "12": "+000000123"}, ("flu_rt", "12")) == 0.0


def test_condition_provider_preserves_alphanumeric_krx_short_code() -> None:
    provider = object.__new__(KiwoomRestConditionProvider)
    items, _, _ = provider._normalize_condition_results(
        {"data": [{"9001": "A0035S0", "302": "빅웨이브로보틱스"}]},
        condition_seq="1",
        condition_name="수급 조건",
    )

    assert items[0]["stock_code"] == "0035S0"
    assert items[0]["stock_code_raw"] == "A0035S0"


def test_market_event_save_resolves_alphanumeric_code_and_updates_same_day_candidate() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE stocks (
                id INTEGER PRIMARY KEY, stock_code TEXT NOT NULL UNIQUE,
                stock_name TEXT NOT NULL, market TEXT, is_active INTEGER NOT NULL
            )
            """
        )
        connection.exec_driver_sql(
            """
            CREATE TABLE market_trend_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, trade_date TEXT NOT NULL,
                stock_id INTEGER NOT NULL, stock_code TEXT, stock_name TEXT, market_type TEXT,
                market_cap INTEGER, trading_value INTEGER, change_rate REAL, intraday_range_rate REAL,
                event_type TEXT NOT NULL, detection_setting_id INTEGER,
                applied_min_market_cap INTEGER, applied_min_trading_value INTEGER,
                applied_min_change_rate REAL, applied_min_intraday_range_rate REAL,
                applied_use_market_cap INTEGER, applied_use_trading_value INTEGER,
                applied_use_change_rate INTEGER, applied_use_intraday_range INTEGER,
                theme_id INTEGER, theme_status TEXT, primary_theme_id INTEGER,
                reason_summary TEXT, user_memo TEXT, is_active INTEGER,
                created_at TEXT, updated_at TEXT, detection_source TEXT,
                condition_seq TEXT, condition_name TEXT, detected_at TEXT, deleted_at TEXT,
                UNIQUE(trade_date, stock_id, event_type)
            )
            """
        )
        connection.execute(
            text("INSERT INTO stocks (id, stock_code, stock_name, market, is_active) VALUES (1, '0035S0', :name, 'KOSDAQ', 1)"),
            {"name": "빅웨이브로보틱스"},
        )

    with Session(engine) as db:
        service = ExternalKiwoomService(db)
        first = service.save_market_events(
            KiwoomMarketEventSaveRequest(
                condition_seq="1",
                condition_name="첫 조건",
                detected_date="2026-10-22",
                items=[{
                    "stock_code": "000350",
                    "stock_code_raw": "A0035S0",
                    "stock_name": "빅웨이브로보틱스",
                    "current_price": 23100,
                    "volume": 100,
                }],
            )
        )
        second = service.save_market_events(
            KiwoomMarketEventSaveRequest(
                condition_seq="2",
                condition_name="다른 조건",
                detected_date="2026-10-22",
                items=[{"stock_code": "000350", "stock_name": "빅웨이브로보틱스"}],
            )
        )
        saved = db.execute(text("SELECT stock_code, condition_seq FROM market_trend_events")).mappings().all()

    assert (first.saved_count, first.unmatched_count) == (1, 0)
    assert (second.updated_count, second.unmatched_count) == (1, 0)
    assert [dict(row) for row in saved] == [{"stock_code": "0035S0", "condition_seq": "2"}]
