from __future__ import annotations

from datetime import date, timedelta
from enum import Enum
from typing import Any, Iterable


class PriceBarTimeframe(str, Enum):
    DAY = "DAY"
    WEEK = "WEEK"
    MONTH = "MONTH"


def _date_value(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _sum_nullable(rows: list[dict[str, Any]], field: str) -> int | None:
    values = [row.get(field) for row in rows if row.get(field) is not None]
    return sum(int(value) for value in values) if values else None


def aggregate_price_bars(
    daily_rows: Iterable[dict[str, Any]],
    timeframe: PriceBarTimeframe | str,
    *,
    cutoff_date: str | date | None = None,
) -> list[dict[str, Any]]:
    """Aggregate daily source rows in memory without persisting derived bars."""
    normalized_timeframe = PriceBarTimeframe(str(getattr(timeframe, "value", timeframe)).upper())
    cutoff = _date_value(cutoff_date) if cutoff_date else None
    rows = sorted(
        (dict(row) for row in daily_rows if cutoff is None or _date_value(row["trade_date"]) <= cutoff),
        key=lambda row: _date_value(row["trade_date"]),
    )
    if normalized_timeframe is PriceBarTimeframe.DAY:
        return rows

    buckets: dict[tuple[int, int] | date, list[dict[str, Any]]] = {}
    for row in rows:
        trading_date = _date_value(row["trade_date"])
        if normalized_timeframe is PriceBarTimeframe.WEEK:
            key: tuple[int, int] | date = trading_date - timedelta(days=trading_date.weekday())
        else:
            key = (trading_date.year, trading_date.month)
        buckets.setdefault(key, []).append(row)

    aggregated: list[dict[str, Any]] = []
    for bucket_rows in buckets.values():
        first = bucket_rows[0]
        last = bucket_rows[-1]
        highs = [float(row["high_price"]) for row in bucket_rows if row.get("high_price") is not None]
        lows = [float(row["low_price"]) for row in bucket_rows if row.get("low_price") is not None]
        aggregated.append(
            {
                # A partial period is dated with its actual last included trading day.
                "trade_date": str(last["trade_date"])[:10],
                "open_price": first.get("open_price"),
                "high_price": max(highs) if highs else None,
                "low_price": min(lows) if lows else None,
                "close_price": last.get("close_price"),
                "volume": _sum_nullable(bucket_rows, "volume"),
                "trading_value": _sum_nullable(bucket_rows, "trading_value"),
            }
        )
    return aggregated


def decorate_price_bars(rows: Iterable[dict[str, Any]], moving_averages: Iterable[int]) -> list[dict[str, Any]]:
    """Calculate simple moving averages from the close of the supplied timeframe."""
    windows = sorted({int(value) for value in moving_averages if int(value) > 0})
    decorated: list[dict[str, Any]] = []
    closes: list[float | None] = []
    for source_row in rows:
        row = dict(source_row)
        close = None if row.get("close_price") is None else float(row["close_price"])
        closes.append(close)
        ma_values: dict[str, float | None] = {}
        for window in windows:
            recent = closes[-window:]
            ma_values[f"ma{window}"] = (
                round(sum(value for value in recent if value is not None) / window, 4)
                if len(recent) == window and all(value is not None for value in recent)
                else None
            )
        decorated.append(
            {
                "trade_date": str(row["trade_date"])[:10],
                "open": row.get("open_price"),
                "high": row.get("high_price"),
                "low": row.get("low_price"),
                "close": row.get("close_price"),
                "volume": row.get("volume"),
                "trading_value": row.get("trading_value"),
                "moving_averages": ma_values,
            }
        )
    return decorated
