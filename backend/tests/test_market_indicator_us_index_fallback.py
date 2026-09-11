from backend.app.providers.market_data.us_daily_price_provider import UsDailyPrice, UsDailyPriceFetchResult
from backend.app.services.market_indicator_service import MarketIndicatorService


class _YahooStub:
    def fetch_recent_daily_prices(self, **_kwargs) -> UsDailyPriceFetchResult:
        return UsDailyPriceFetchResult(
            prices=[
                UsDailyPrice("2026-09-09", 100, 102, 99, 101, 10),
                UsDailyPrice("2026-09-10", 101, 104, 100, 103, 20),
            ],
            history_exhausted=True,
        )


def test_yahoo_supplements_only_sessions_newer_than_fred() -> None:
    service = MarketIndicatorService.__new__(MarketIndicatorService)
    service.yahoo_us = _YahooStub()
    fred = [{
        "indicator_code": "US_SP500",
        "value_date": "2026-09-09",
        "value": 101.0,
        "source_provider": "FRED",
    }]

    rows, added = service._supplement_us_index_from_yahoo(
        "US_SP500",
        fred,
        start_date="2026-09-01",
        end_date="2026-09-11",
    )

    assert added == 1
    assert [row["value_date"] for row in rows] == ["2026-09-09", "2026-09-10"]
    assert rows[-1]["source_provider"] == "YFINANCE"
    assert rows[-1]["value"] == 103
    assert rows[-1]["change_value"] == 2
    assert round(rows[-1]["change_pct"], 6) == round(2 / 101 * 100, 6)


def test_yahoo_does_not_replace_same_day_fred_value() -> None:
    service = MarketIndicatorService.__new__(MarketIndicatorService)
    service.yahoo_us = _YahooStub()
    fred = [{"indicator_code": "US_SP500", "value_date": "2026-09-10", "value": 102.5}]

    rows, added = service._supplement_us_index_from_yahoo(
        "US_SP500",
        fred,
        start_date="2026-09-01",
        end_date="2026-09-11",
    )

    assert added == 0
    assert rows == fred
