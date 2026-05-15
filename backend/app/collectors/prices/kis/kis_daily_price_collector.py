from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, timedelta

from backend.app.collectors.prices.kis.kis_client import KisClient
from backend.app.core.config import KIS_DAILY_MAX_ROWS

logger = logging.getLogger(__name__)


@dataclass
class KisDailyPriceRow:
    trade_date: str
    open_price: float | None
    high_price: float | None
    low_price: float | None
    close_price: float | None
    change_price: float | None
    change_rate: float | None
    volume: int | None
    trading_value: int | None
    source: str = "broker_kis"


def normalize_stock_code_for_broker(stock_code: str) -> str:
    value = (stock_code or "").strip()
    if len(value) == 7 and value[0].upper() == "A" and value[1:].isdigit():
        return value[1:]
    return value


class KisDailyPriceCollector:
    def __init__(self) -> None:
        self.client = KisClient()
        self.max_rows = KIS_DAILY_MAX_ROWS

    @property
    def name(self) -> str:
        return "kis_daily_price_collector"

    @staticmethod
    def _to_float(value: str | int | float | None) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(str(value).replace(",", ""))
        except ValueError:
            return None

    @staticmethod
    def _to_int(value: str | int | float | None) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(float(str(value).replace(",", "")))
        except ValueError:
            return None

    @staticmethod
    def _date_yyyymmdd_to_iso(value: str) -> str:
        raw = (value or "").strip()
        if len(raw) == 8 and raw.isdigit():
            return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
        return raw

    def _map_output_row(self, item: dict) -> KisDailyPriceRow:
        close_price = self._to_float(item.get("stck_clpr"))
        open_price = self._to_float(item.get("stck_oprc"))
        high_price = self._to_float(item.get("stck_hgpr"))
        low_price = self._to_float(item.get("stck_lwpr"))
        previous_close = self._to_float(item.get("stck_prdy_clpr"))
        change_price = self._to_float(item.get("prdy_vrss"))
        change_rate = self._to_float(item.get("prdy_ctrt"))
        if change_price is None and close_price is not None and previous_close is not None:
            change_price = close_price - previous_close
        if change_rate is None and change_price is not None and previous_close not in (None, 0):
            change_rate = round((change_price / previous_close) * 100, 4)
        volume = self._to_int(item.get("acml_vol"))
        trading_value = self._to_int(item.get("acml_tr_pbmn"))
        if trading_value is None and close_price is not None and volume is not None:
            trading_value = int(close_price * volume)
        return KisDailyPriceRow(
            trade_date=self._date_yyyymmdd_to_iso(str(item.get("stck_bsop_date") or "")),
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
            change_price=change_price,
            change_rate=change_rate,
            volume=volume,
            trading_value=trading_value,
            source="broker_kis",
        )

    def collect_daily(self, stock_code: str, start_date: date, end_date: date, max_calls: int = 8) -> tuple[str, list[KisDailyPriceRow]]:
        normalized = normalize_stock_code_for_broker(stock_code)
        if not normalized:
            return normalized, []

        chunk_days = max(40, self.max_rows + 20)
        rows_by_date: dict[str, KisDailyPriceRow] = {}
        calls = 0
        cursor_start = start_date
        while cursor_start <= end_date and calls < max_calls:
            cursor_end = min(end_date, cursor_start + timedelta(days=chunk_days - 1))
            payload = self.client.get_daily_prices(
                stock_code=normalized,
                start_date=cursor_start.strftime("%Y%m%d"),
                end_date=cursor_end.strftime("%Y%m%d"),
                adjusted=True,
            )
            output2 = payload.get("output2") or []
            if not isinstance(output2, list):
                output2 = []
            for item in output2:
                try:
                    mapped = self._map_output_row(item)
                except Exception:
                    continue
                if mapped.trade_date:
                    rows_by_date[mapped.trade_date] = mapped
            logger.info(
                "[KIS] stock_code=%s normalized=%s start=%s end=%s calls=%s fetched=%s",
                stock_code,
                normalized,
                cursor_start,
                cursor_end,
                calls + 1,
                len(output2),
            )
            calls += 1
            cursor_start = cursor_end + timedelta(days=1)
            time.sleep(0.2)

        rows = [rows_by_date[key] for key in sorted(rows_by_date.keys())]
        return normalized, rows
