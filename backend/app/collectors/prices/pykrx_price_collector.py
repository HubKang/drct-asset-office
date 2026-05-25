from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from backend.app.core.config import PYKRX_DISABLE_PROXY
from backend.app.utils.stock_code_utils import is_valid_kr_stock_code, normalize_kr_stock_code

logger = logging.getLogger(__name__)


def normalize_stock_code_for_pykrx(stock_code: str) -> str:
    value = normalize_kr_stock_code(stock_code)
    if is_valid_kr_stock_code(value):
        return value
    return ""


@dataclass
class PykrxDailyPriceRow:
    trade_date: str
    open_price: float | None
    high_price: float | None
    low_price: float | None
    close_price: float | None
    change_price: float | None
    change_rate: float | None
    volume: int | None
    trading_value: int | None
    source: str = "pykrx"


class PykrxPriceCollector:
    @property
    def name(self) -> str:
        return "pykrx_price_collector"

    @staticmethod
    def _to_float(value) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except Exception:
            return None

    @staticmethod
    def _to_int(value) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except Exception:
            return None

    @staticmethod
    def _fmt_date(value) -> str:
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")
        if hasattr(value, "strftime"):
            return value.strftime("%Y-%m-%d")
        raw = str(value)
        if len(raw) == 8 and raw.isdigit():
            return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
        return raw[:10]

    @staticmethod
    def _pick_value(row, *keys):
        for key in keys:
            if key in row:
                return row.get(key)
        return None

    def collect_daily(self, stock_code: str, start_date: date, end_date: date, adjusted: bool = True) -> tuple[str, list[PykrxDailyPriceRow]]:
        normalized = normalize_stock_code_for_pykrx(stock_code)
        if not normalized:
            raise ValueError(f"INVALID_STOCK_CODE raw={stock_code} normalized={normalize_kr_stock_code(stock_code)}")

        mpl_dir = Path.cwd() / ".mpltcache"
        mpl_dir.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("MPLCONFIGDIR", str(mpl_dir.resolve()))

        disable_proxy = PYKRX_DISABLE_PROXY
        proxy_keys = ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]
        previous_proxy_values = {k: os.environ.get(k) for k in proxy_keys} if disable_proxy else {}

        try:
            from pykrx import stock
        except Exception as exc:
            raise ValueError("pykrx package is not installed. Run 'pip install pykrx' and retry.") from exc

        try:
            if disable_proxy:
                for key in proxy_keys:
                    os.environ.pop(key, None)
                os.environ["NO_PROXY"] = "*"

            logger.info(
                "PyKRX daily request start: raw_code=%s normalized=%s start=%s end=%s adjusted=%s disable_proxy=%s",
                stock_code,
                normalized,
                start_date.isoformat(),
                end_date.isoformat(),
                adjusted,
                disable_proxy,
            )

            try:
                df = stock.get_market_ohlcv_by_date(
                    fromdate=start_date.strftime("%Y%m%d"),
                    todate=end_date.strftime("%Y%m%d"),
                    ticker=normalized,
                    adjusted=adjusted,
                )
            except Exception as exc:
                logger.exception(
                    "PyKRX 일봉 조회 실패: raw_code=%s normalized=%s start=%s end=%s adjusted=%s error=%s",
                    stock_code,
                    normalized,
                    start_date.isoformat(),
                    end_date.isoformat(),
                    adjusted,
                    exc,
                )
                raise RuntimeError(
                    f"PYKRX_REQUEST_FAILED raw={stock_code} normalized={normalized} "
                    f"start={start_date.isoformat()} end={end_date.isoformat()} "
                    f"error={type(exc).__name__}: {str(exc)}"
                ) from exc

            logger.debug("PyKRX raw columns: normalized=%s columns=%s", normalized, list(df.columns) if df is not None else None)
        finally:
            if disable_proxy:
                for key, value in previous_proxy_values.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value

        if df is None or df.empty:
            logger.warning(
                "PyKRX 일봉 데이터 없음: raw_code=%s normalized=%s start=%s end=%s",
                stock_code,
                normalized,
                start_date.isoformat(),
                end_date.isoformat(),
            )
            return normalized, []

        rows: list[PykrxDailyPriceRow] = []
        prev_close: float | None = None
        for idx, row in df.iterrows():
            open_price = self._to_float(self._pick_value(row, "시가"))
            high_price = self._to_float(self._pick_value(row, "고가"))
            low_price = self._to_float(self._pick_value(row, "저가"))
            close_price = self._to_float(self._pick_value(row, "종가"))
            volume = self._to_int(self._pick_value(row, "거래량"))
            trading_value = self._to_int(self._pick_value(row, "거래대금"))

            change_price = self._to_float(self._pick_value(row, "대비"))
            change_rate = self._to_float(self._pick_value(row, "등락률"))
            if change_price is None and close_price is not None and prev_close is not None:
                change_price = close_price - prev_close
            if change_rate is None and change_price is not None and prev_close not in (None, 0):
                change_rate = round((change_price / prev_close) * 100, 4)

            rows.append(
                PykrxDailyPriceRow(
                    trade_date=self._fmt_date(idx),
                    open_price=open_price,
                    high_price=high_price,
                    low_price=low_price,
                    close_price=close_price,
                    change_price=change_price,
                    change_rate=change_rate,
                    volume=volume,
                    trading_value=trading_value,
                )
            )
            prev_close = close_price

        logger.info(
            "PyKRX daily request done: raw_code=%s normalized=%s rows=%s start=%s end=%s",
            stock_code,
            normalized,
            len(rows),
            start_date.isoformat(),
            end_date.isoformat(),
        )
        return normalized, rows
