from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Callable, Iterable
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

from backend.app.providers.market_data.us_daily_price_provider import (
    UsDailyPrice,
    UsDailyPriceFetchResult,
    UsDailyPriceValidationError,
    normalize_and_validate_us_daily_price,
)


logger = logging.getLogger(__name__)
_NY = ZoneInfo("America/New_York")

# Only verified class-share exceptions belong here. Do not globally rewrite dots.
YAHOO_SYMBOL_OVERRIDES = {
    "BRK.B": "BRK-B",
    "BF.B": "BF-B",
}


@dataclass(frozen=True)
class YFinanceBatchFetchResult:
    results: dict[str, UsDailyPriceFetchResult]
    failures: dict[str, str]


def is_us_daily_row_complete(trade_date: str, *, now: datetime | None = None) -> bool:
    """Conservatively reject the current NY trading-day row until after close.

    Yahoo defines the actual session dates, so this helper never synthesizes a
    weekend or holiday row. Early-close rows are accepted later at 16:15 ET;
    that delay is intentional and safer than storing an unfinished candle.
    """

    current = now.astimezone(_NY) if now else datetime.now(_NY)
    row_date = date.fromisoformat(trade_date)
    if row_date < current.date():
        return True
    if row_date > current.date() or row_date.weekday() >= 5:
        return False
    return current.time() >= time(16, 15)


class YFinanceUsDailyPriceProvider:
    """Regular-session raw US daily OHLCV provider.

    Raw Yahoo DataFrames stay transient. Only normalized, validated candles are
    returned to the service layer.
    """

    def __init__(
        self,
        *,
        downloader: Callable[..., pd.DataFrame] | None = None,
        batch_size: int = 30,
        retry_count: int = 2,
        now_factory: Callable[[], datetime] | None = None,
    ) -> None:
        self._downloader = downloader or yf.download
        self.batch_size = max(1, min(batch_size, 40))
        self.retry_count = max(0, min(retry_count, 2))
        self._now_factory = now_factory or (lambda: datetime.now(_NY))

    @staticmethod
    def yahoo_symbol(symbol: str) -> str:
        normalized = str(symbol or "").strip().upper()
        if not normalized:
            raise ValueError("symbol_missing")
        return YAHOO_SYMBOL_OVERRIDES.get(normalized, normalized)

    def _download(self, symbols: list[str]) -> pd.DataFrame:
        tickers: str | list[str] = symbols[0] if len(symbols) == 1 else symbols
        return self._downloader(
            tickers=tickers,
            period="2y",
            interval="1d",
            auto_adjust=False,
            prepost=False,
            actions=False,
            repair=False,
            group_by="ticker",
            threads=True,
            progress=False,
        )

    @staticmethod
    def _frame_for_symbol(data: pd.DataFrame, yahoo_symbol: str) -> pd.DataFrame:
        if data is None or data.empty:
            raise ValueError("price_history_missing")
        if isinstance(data.columns, pd.MultiIndex):
            first = set(str(value) for value in data.columns.get_level_values(0))
            second = set(str(value) for value in data.columns.get_level_values(1))
            if yahoo_symbol in first:
                return data[yahoo_symbol].copy()
            if yahoo_symbol in second:
                return data.xs(yahoo_symbol, axis=1, level=1).copy()
            raise ValueError("ticker_missing_from_batch")
        return data.copy()

    def _parse_frame(self, frame: pd.DataFrame, *, symbol: str, trading_days: int) -> UsDailyPriceFetchResult:
        required = ("Open", "High", "Low", "Close", "Volume")
        if any(column not in frame.columns for column in required):
            raise ValueError("daily_ohlcv_columns_missing")
        seen_dates: set[str] = set()
        prices: list[UsDailyPrice] = []
        normalized_dates: set[str] = set()
        incomplete_row_count = 0
        now = self._now_factory()
        for index, values in frame.sort_index().iterrows():
            if all(pd.isna(values[column]) for column in required):
                continue
            timestamp = pd.Timestamp(index)
            trade_date = timestamp.date().isoformat()
            if not is_us_daily_row_complete(trade_date, now=now):
                continue
            if any(pd.isna(values[column]) for column in required):
                incomplete_row_count += 1
                missing = ",".join(column for column in required if pd.isna(values[column]))
                logger.warning(
                    "Yahoo US daily incomplete candle skipped symbol=%s trade_date=%s missing=%s",
                    symbol,
                    trade_date,
                    missing,
                )
                continue
            if trade_date in seen_dates:
                raise UsDailyPriceValidationError(f"{trade_date}: duplicate daily candle")
            seen_dates.add(trade_date)
            row = UsDailyPrice(
                trade_date=trade_date,
                open_price=float(values["Open"]),
                high_price=float(values["High"]),
                low_price=float(values["Low"]),
                close_price=float(values["Close"]),
                volume=int(values["Volume"]),
            )
            row, normalized = normalize_and_validate_us_daily_price(row)
            if normalized:
                normalized_dates.add(trade_date)
                logger.info("NORMALIZED_OPEN_BOUNDARY symbol=%s trade_date=%s", symbol, trade_date)
            prices.append(row)
        if not prices:
            raise ValueError("completed_daily_price_missing")
        selected = prices[-trading_days:]
        # The diagnostic count applies to the rows returned to the caller.
        returned_normalized_count = sum(row.trade_date in normalized_dates for row in selected)
        return UsDailyPriceFetchResult(
            prices=selected,
            history_exhausted=True,
            normalized_open_boundary_count=returned_normalized_count,
            incomplete_row_count=incomplete_row_count,
        )

    def _parse_download(
        self,
        data: pd.DataFrame,
        symbol_map: dict[str, str],
        *,
        trading_days: int,
    ) -> tuple[dict[str, UsDailyPriceFetchResult], dict[str, str]]:
        results: dict[str, UsDailyPriceFetchResult] = {}
        failures: dict[str, str] = {}
        for symbol, yahoo_symbol in symbol_map.items():
            try:
                frame = self._frame_for_symbol(data, yahoo_symbol)
                results[symbol] = self._parse_frame(frame, symbol=symbol, trading_days=trading_days)
            except Exception as exc:
                failures[symbol] = str(exc)[:200]
        return results, failures

    @staticmethod
    def _chunks(values: list[str], size: int) -> Iterable[list[str]]:
        for index in range(0, len(values), size):
            yield values[index : index + size]

    def fetch_many_history(self, *, symbols: list[str], trading_days: int) -> YFinanceBatchFetchResult:
        normalized = list(dict.fromkeys(str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()))
        results: dict[str, UsDailyPriceFetchResult] = {}
        failures: dict[str, str] = {}
        for batch in self._chunks(normalized, self.batch_size):
            symbol_map = {symbol: self.yahoo_symbol(symbol) for symbol in batch}
            try:
                data = self._download(list(symbol_map.values()))
                parsed, missing = self._parse_download(data, symbol_map, trading_days=trading_days)
                results.update(parsed)
                failures.update(missing)
            except Exception as exc:
                for symbol in batch:
                    failures[symbol] = str(exc)[:200]

        # Retry only missing symbols, individually, without disturbing successful data.
        for _ in range(self.retry_count):
            retry_symbols = [
                symbol
                for symbol in normalized
                if symbol not in results or results[symbol].incomplete_row_count > 0
            ]
            if not retry_symbols:
                break
            for symbol in retry_symbols:
                try:
                    yahoo_symbol = self.yahoo_symbol(symbol)
                    data = self._download([yahoo_symbol])
                    parsed, missing = self._parse_download(data, {symbol: yahoo_symbol}, trading_days=trading_days)
                    if symbol in parsed:
                        results[symbol] = parsed[symbol]
                        failures.pop(symbol, None)
                    elif symbol in missing:
                        failures[symbol] = missing[symbol]
                except Exception as exc:
                    failures[symbol] = str(exc)[:200]

        for symbol, reason in failures.items():
            logger.warning("Yahoo US daily price unavailable symbol=%s error=%s", symbol, reason)
        return YFinanceBatchFetchResult(results=results, failures=failures)

    def fetch_history(self, *, symbol: str, exchange: str, start_date: str, trading_days: int) -> UsDailyPriceFetchResult:
        del exchange, start_date
        batch = self.fetch_many_history(symbols=[symbol], trading_days=trading_days)
        normalized = str(symbol).strip().upper()
        if normalized not in batch.results:
            raise ValueError(batch.failures.get(normalized, "price_history_missing"))
        return batch.results[normalized]

    def fetch_recent_daily_prices(self, *, symbol: str, exchange: str, trading_days: int = 10) -> UsDailyPriceFetchResult:
        return self.fetch_history(symbol=symbol, exchange=exchange, start_date="", trading_days=trading_days)

    def fetch_daily_prices(self, *, symbol: str, exchange: str, trading_days: int = 260) -> UsDailyPriceFetchResult:
        return self.fetch_history(symbol=symbol, exchange=exchange, start_date="", trading_days=trading_days)
