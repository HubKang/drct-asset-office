from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import date


@dataclass(frozen=True)
class UsDailyPrice:
    trade_date: str
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: int


@dataclass(frozen=True)
class UsDailyPriceFetchResult:
    prices: list[UsDailyPrice]
    history_exhausted: bool
    normalized_open_boundary_count: int = 0


class UsDailyPriceValidationError(ValueError):
    pass


class UsHistoricalPricePartialError(RuntimeError):
    def __init__(self, prices: list[UsDailyPrice], reason: str) -> None:
        super().__init__(reason)
        self.prices = prices


def normalize_and_validate_us_daily_price(row: UsDailyPrice) -> tuple[UsDailyPrice, bool]:
    try:
        date.fromisoformat(row.trade_date)
    except (TypeError, ValueError) as exc:
        raise UsDailyPriceValidationError("trade_date is missing or invalid") from exc

    values = (row.open_price, row.high_price, row.low_price, row.close_price)
    if not all(math.isfinite(value) and value > 0 for value in values):
        raise UsDailyPriceValidationError(f"{row.trade_date}: OHLC must be finite and positive")
    if not row.low_price <= row.high_price:
        raise UsDailyPriceValidationError(f"{row.trade_date}: low exceeds high")
    if not row.low_price <= row.close_price <= row.high_price:
        raise UsDailyPriceValidationError(f"{row.trade_date}: close is outside low/high")
    if row.volume < 0:
        raise UsDailyPriceValidationError(f"{row.trade_date}: volume is negative")

    normalized = not row.low_price <= row.open_price <= row.high_price
    if normalized:
        row = replace(
            row,
            high_price=max(row.high_price, row.open_price, row.close_price),
            low_price=min(row.low_price, row.open_price, row.close_price),
        )
    return row, normalized


def validate_us_daily_price(row: UsDailyPrice) -> None:
    """Reject critical daily-candle errors without rejecting Open-only boundaries."""

    normalize_and_validate_us_daily_price(row)
