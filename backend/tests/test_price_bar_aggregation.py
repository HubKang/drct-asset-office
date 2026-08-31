from __future__ import annotations

from datetime import date, timedelta

from backend.app.services.price_bar_aggregation import (
    PriceBarTimeframe,
    aggregate_price_bars,
    decorate_price_bars,
)


def price(day: str, close: float, *, open_price: float | None = None, high: float | None = None,
          low: float | None = None, volume: int = 100, trading_value: int = 1_000) -> dict:
    return {
        "trade_date": day,
        "open_price": close if open_price is None else open_price,
        "high_price": close if high is None else high,
        "low_price": close if low is None else low,
        "close_price": close,
        "volume": volume,
        "trading_value": trading_value,
    }


def test_weekly_ohlcv_uses_actual_last_trading_day_and_monday_bucket() -> None:
    rows = [
        price("2026-08-24", 11, open_price=10, high=12, low=9, volume=10, trading_value=100),
        price("2026-08-26", 13, high=15, low=10, volume=20, trading_value=200),
        price("2026-08-28", 12, high=14, low=8, volume=30, trading_value=300),
        price("2026-08-31", 17, open_price=16, high=18, low=15, volume=40, trading_value=400),
    ]

    bars = aggregate_price_bars(rows, PriceBarTimeframe.WEEK)

    assert bars == [
        {
            "trade_date": "2026-08-28", "open_price": 10, "high_price": 15.0,
            "low_price": 8.0, "close_price": 12, "volume": 60, "trading_value": 600,
        },
        {
            "trade_date": "2026-08-31", "open_price": 16, "high_price": 18.0,
            "low_price": 15.0, "close_price": 17, "volume": 40, "trading_value": 400,
        },
    ]


def test_partial_week_and_month_never_include_rows_after_cutoff() -> None:
    rows = [
        price("2026-08-27", 10, high=11, volume=10),
        price("2026-08-28", 99, high=120, volume=900),
        price("2026-09-01", 200, high=220, volume=2_000),
    ]

    weekly = aggregate_price_bars(rows, "WEEK", cutoff_date="2026-08-27")
    monthly = aggregate_price_bars(rows, "MONTH", cutoff_date="2026-08-28")

    assert weekly[-1]["trade_date"] == "2026-08-27"
    assert weekly[-1]["high_price"] == 11.0
    assert weekly[-1]["volume"] == 10
    assert monthly[-1]["trade_date"] == "2026-08-28"
    assert monthly[-1]["close_price"] == 99
    assert all(bar["trade_date"] < "2026-09-01" for bar in monthly)


def test_holiday_week_uses_first_and_last_existing_trading_days() -> None:
    rows = [
        price("2026-09-15", 103, open_price=100, high=105, low=98),
        price("2026-09-16", 106, high=108, low=101),
        price("2026-09-18", 112, high=113, low=107),
    ]

    bar = aggregate_price_bars(rows, "WEEK")[0]

    assert bar["open_price"] == 100
    assert bar["close_price"] == 112
    assert bar["trade_date"] == "2026-09-18"


def test_monthly_ohlcv_uses_first_open_last_close_and_sums() -> None:
    rows = [
        price("2026-06-01", 103, open_price=100, high=105, low=98, volume=10, trading_value=100),
        price("2026-06-15", 107, high=111, low=101, volume=20, trading_value=200),
        price("2026-06-30", 112, high=113, low=108, volume=30, trading_value=300),
    ]

    bar = aggregate_price_bars(rows, "MONTH")[0]

    assert bar == {
        "trade_date": "2026-06-30", "open_price": 100, "high_price": 113.0,
        "low_price": 98.0, "close_price": 112, "volume": 60, "trading_value": 600,
    }


def test_weekly_and_monthly_sma_are_recomputed_from_aggregated_closes() -> None:
    weekly_source = [price((date(2026, 1, 5) + timedelta(days=7 * index)).isoformat(), index + 1) for index in range(20)]
    monthly_source = [price(date(2024 + index // 12, index % 12 + 1, 15).isoformat(), index + 1) for index in range(20)]

    weekly = decorate_price_bars(aggregate_price_bars(weekly_source, "WEEK"), [10, 20])
    monthly = decorate_price_bars(aggregate_price_bars(monthly_source, "MONTH"), [10, 20])

    assert weekly[8]["moving_averages"]["ma10"] is None
    assert weekly[9]["moving_averages"]["ma10"] == 5.5
    assert weekly[19]["moving_averages"]["ma20"] == 10.5
    assert monthly[18]["moving_averages"]["ma20"] is None
    assert monthly[19]["moving_averages"]["ma20"] == 10.5


def test_day_timeframe_preserves_source_candles_and_ma_behavior() -> None:
    source = [price("2026-08-27", 10), price("2026-08-28", 20)]

    day_rows = aggregate_price_bars(source, "DAY", cutoff_date="2026-08-28")
    decorated = decorate_price_bars(day_rows, [2])

    assert day_rows == source
    assert decorated[0]["moving_averages"]["ma2"] is None
    assert decorated[1]["moving_averages"]["ma2"] == 15.0
