from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import math
import pandas as pd
import pytest

from backend.app.providers.market_data.us_daily_price_provider import (
    UsDailyPrice,
    UsDailyPriceValidationError,
    normalize_and_validate_us_daily_price,
    validate_us_daily_price,
)
from backend.app.providers.market_data.yfinance_us_daily_price_provider import (
    YFinanceUsDailyPriceProvider,
    is_us_daily_row_complete,
)


NY = ZoneInfo("America/New_York")
FIELDS = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]


def _single_frame(close: float = 209.79) -> pd.DataFrame:
    return pd.DataFrame(
        [
            [211.03, 214.73, 210.11, 213.05, 213.05, 100],
            [212.42, 213.60, 209.23, close, close, 200],
        ],
        index=pd.to_datetime(["2026-08-25", "2026-08-26"]),
        columns=FIELDS,
    )


def _multi_frame() -> pd.DataFrame:
    columns = pd.MultiIndex.from_product([["NVDA", "COIN"], FIELDS], names=["Ticker", "Price"])
    values = [
        [212.42, 213.60, 209.23, 209.79, 209.79, 200, 176.0, 189.27, 174.73, 187.18, 187.18, 300]
    ]
    return pd.DataFrame(values, index=pd.to_datetime(["2026-08-26"]), columns=columns)


def test_yfinance_single_ticker_uses_explicit_regular_raw_daily_parameters() -> None:
    calls: list[dict] = []

    def download(**kwargs):
        calls.append(kwargs)
        return _single_frame()

    provider = YFinanceUsDailyPriceProvider(
        downloader=download,
        retry_count=0,
        now_factory=lambda: datetime(2026, 8, 27, 9, tzinfo=NY),
    )
    result = provider.fetch_history(symbol="NVDA", exchange="NASDAQ", start_date="", trading_days=2)
    assert [row.trade_date for row in result.prices] == ["2026-08-25", "2026-08-26"]
    assert result.prices[-1].close_price == 209.79
    assert calls[0]["interval"] == "1d"
    assert calls[0]["auto_adjust"] is False
    assert calls[0]["prepost"] is False
    assert calls[0]["actions"] is False
    assert calls[0]["repair"] is False


def test_yfinance_multi_ticker_parsing_keeps_pandas_out_of_service_layer() -> None:
    provider = YFinanceUsDailyPriceProvider(
        downloader=lambda **_kwargs: _multi_frame(),
        retry_count=0,
        now_factory=lambda: datetime(2026, 8, 27, 9, tzinfo=NY),
    )
    batch = provider.fetch_many_history(symbols=["NVDA", "COIN"], trading_days=20)
    assert not batch.failures
    assert batch.results["NVDA"].prices[0].close_price == 209.79
    assert batch.results["COIN"].prices[0].close_price == 187.18


def test_yfinance_missing_ticker_isolated_from_successful_batch() -> None:
    provider = YFinanceUsDailyPriceProvider(
        downloader=lambda **_kwargs: _multi_frame(),
        retry_count=0,
        now_factory=lambda: datetime(2026, 8, 27, 9, tzinfo=NY),
    )
    batch = provider.fetch_many_history(symbols=["NVDA", "MISSING"], trading_days=20)
    assert "NVDA" in batch.results
    assert batch.failures["MISSING"] == "ticker_missing_from_batch"


def test_yfinance_rejects_nan_invalid_candle_and_duplicate_date() -> None:
    nan_frame = _single_frame()
    nan_frame.loc[pd.Timestamp("2026-08-26"), "Close"] = math.nan
    invalid_frame = _single_frame(close=218.94)
    duplicate_frame = pd.concat([_single_frame(), _single_frame().tail(1)])
    frames = iter([nan_frame, invalid_frame, duplicate_frame])
    provider = YFinanceUsDailyPriceProvider(
        downloader=lambda **_kwargs: next(frames),
        retry_count=0,
        now_factory=lambda: datetime(2026, 8, 27, 9, tzinfo=NY),
    )
    partial = provider.fetch_many_history(symbols=["NVDA"], trading_days=20)
    assert "NVDA" in partial.results
    assert partial.results["NVDA"].incomplete_row_count == 1
    assert [row.trade_date for row in partial.results["NVDA"].prices] == ["2026-08-25"]
    for expected in ("outside low/high", "duplicate"):
        batch = provider.fetch_many_history(symbols=["NVDA"], trading_days=20)
        assert expected in batch.failures["NVDA"]


def test_yfinance_skips_only_incomplete_candle_and_keeps_valid_history() -> None:
    frame = _single_frame()
    frame.loc[pd.Timestamp("2026-08-26"), "Volume"] = math.nan
    frame.loc[pd.Timestamp("2026-08-27")] = [210.0, 212.0, 208.0, 211.0, 211.0, 300]
    provider = YFinanceUsDailyPriceProvider(
        downloader=lambda **_kwargs: frame,
        retry_count=0,
        now_factory=lambda: datetime(2026, 8, 28, 9, tzinfo=NY),
    )

    result = provider.fetch_history(symbol="NVDA", exchange="NASDAQ", start_date="", trading_days=20)

    assert [row.trade_date for row in result.prices] == ["2026-08-25", "2026-08-27"]
    assert result.incomplete_row_count == 1


def test_current_new_york_daily_row_is_not_treated_as_final() -> None:
    before_close = YFinanceUsDailyPriceProvider(
        downloader=lambda **_kwargs: _single_frame(),
        retry_count=0,
        now_factory=lambda: datetime(2026, 8, 26, 15, 59, tzinfo=NY),
    )
    result = before_close.fetch_history(symbol="NVDA", exchange="NASDAQ", start_date="", trading_days=2)
    assert [row.trade_date for row in result.prices] == ["2026-08-25"]
    assert not is_us_daily_row_complete("2026-08-26", now=datetime(2026, 8, 26, 13, 30, tzinfo=NY))
    assert is_us_daily_row_complete("2026-08-26", now=datetime(2026, 8, 26, 16, 20, tzinfo=NY))
    assert not is_us_daily_row_complete("2026-08-29", now=datetime(2026, 8, 29, 18, 0, tzinfo=NY))


def test_current_incomplete_new_york_row_is_ignored_without_marking_history_partial() -> None:
    frame = _single_frame()
    frame.loc[pd.Timestamp("2026-08-26"), "Volume"] = math.nan
    provider = YFinanceUsDailyPriceProvider(
        downloader=lambda **_kwargs: frame,
        retry_count=0,
        now_factory=lambda: datetime(2026, 8, 26, 15, 59, tzinfo=NY),
    )

    result = provider.fetch_history(symbol="NVDA", exchange="NASDAQ", start_date="", trading_days=2)

    assert [row.trade_date for row in result.prices] == ["2026-08-25"]
    assert result.incomplete_row_count == 0


def test_incomplete_batch_candle_is_retried_individually() -> None:
    incomplete = _single_frame()
    incomplete.loc[pd.Timestamp("2026-08-26"), "Volume"] = math.nan
    frames = iter([incomplete, _single_frame()])
    provider = YFinanceUsDailyPriceProvider(
        downloader=lambda **_kwargs: next(frames),
        retry_count=1,
        now_factory=lambda: datetime(2026, 8, 27, 9, tzinfo=NY),
    )

    result = provider.fetch_history(symbol="NVDA", exchange="NASDAQ", start_date="", trading_days=2)

    assert [row.trade_date for row in result.prices] == ["2026-08-25", "2026-08-26"]
    assert result.incomplete_row_count == 0


def test_common_candle_validation_allows_zero_volume_but_rejects_negative() -> None:
    validate_us_daily_price(UsDailyPrice("2026-08-26", 10, 11, 9, 10, 0))
    try:
        validate_us_daily_price(UsDailyPrice("2026-08-26", 10, 11, 9, 10, -1))
        raise AssertionError("negative volume must be rejected")
    except UsDailyPriceValidationError:
        pass


@pytest.mark.parametrize(
    ("row", "expected_low", "expected_high"),
    [
        (UsDailyPrice("2026-08-26", 8, 11, 9, 10, 1), 8, 11),
        (UsDailyPrice("2026-08-26", 12, 11, 9, 10, 1), 9, 12),
    ],
)
def test_open_boundary_is_normalized_without_changing_close_or_volume(
    row: UsDailyPrice,
    expected_low: float,
    expected_high: float,
) -> None:
    normalized, changed = normalize_and_validate_us_daily_price(row)
    assert changed is True
    assert normalized.low_price == expected_low
    assert normalized.high_price == expected_high
    assert normalized.close_price == row.close_price
    assert normalized.volume == row.volume
    assert normalized.low_price <= normalized.open_price <= normalized.high_price
    assert normalized.low_price <= normalized.close_price <= normalized.high_price


@pytest.mark.parametrize(
    "row",
    [
        UsDailyPrice("2026-08-26", 10, 11, 9, 12, 1),
        UsDailyPrice("2026-08-26", 10, 11, 9, 8, 1),
        UsDailyPrice("2026-08-26", 10, 11, 9, math.nan, 1),
        UsDailyPrice("2026-08-26", 10, 11, 9, 0, 1),
        UsDailyPrice("2026-08-26", 10, 11, 9, 10, -1),
    ],
)
def test_close_critical_errors_and_negative_volume_are_rejected(row: UsDailyPrice) -> None:
    with pytest.raises(UsDailyPriceValidationError):
        normalize_and_validate_us_daily_price(row)


def test_provider_reports_open_boundary_normalization() -> None:
    frame = _single_frame()
    frame.loc[pd.Timestamp("2026-08-26"), "Open"] = 208.0
    provider = YFinanceUsDailyPriceProvider(
        downloader=lambda **_kwargs: frame,
        retry_count=0,
        now_factory=lambda: datetime(2026, 8, 27, 9, tzinfo=NY),
    )
    result = provider.fetch_history(symbol="NVDA", exchange="NASDAQ", start_date="", trading_days=2)
    assert result.normalized_open_boundary_count == 1
    assert result.prices[-1].low_price == 208.0
