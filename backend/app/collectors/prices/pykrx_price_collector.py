from __future__ import annotations

import os
import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path


logger = logging.getLogger(__name__)


def normalize_stock_code_for_pykrx(stock_code: str) -> str:
    value = (stock_code or "").strip()
    if len(value) == 7 and value[0].upper() == "A" and value[1:].isdigit():
        return value[1:]
    return value


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
            raise ValueError("PyKRX 조회용 종목코드 정규화에 실패했습니다.")

        mpl_dir = Path.cwd() / ".mpltcache"
        mpl_dir.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("MPLCONFIGDIR", str(mpl_dir.resolve()))

        proxy_keys = ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]
        previous_proxy_values = {k: os.environ.get(k) for k in proxy_keys}
        try:
            from pykrx import stock
        except Exception as exc:
            raise ValueError("pykrx 패키지가 설치되어 있지 않습니다. pip install pykrx 후 다시 실행해 주세요.") from exc

        try:
            for key in proxy_keys:
                if key in os.environ:
                    del os.environ[key]
            os.environ["NO_PROXY"] = "*"
            logger.info(
                "PyKRX 일봉 조회 시작: stock_code=%s normalized=%s start=%s end=%s adjusted=%s",
                stock_code,
                normalized,
                start_date.isoformat(),
                end_date.isoformat(),
                adjusted,
            )
            df = stock.get_market_ohlcv_by_date(
                fromdate=start_date.strftime("%Y%m%d"),
                todate=end_date.strftime("%Y%m%d"),
                ticker=normalized,
                adjusted=adjusted,
            )
            logger.debug("PyKRX 원천 컬럼: normalized=%s columns=%s", normalized, list(df.columns) if df is not None else None)
        finally:
            for key, value in previous_proxy_values.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        if df is None or df.empty:
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
            "PyKRX 일봉 조회 완료: normalized=%s rows=%s start=%s end=%s",
            normalized,
            len(rows),
            start_date.isoformat(),
            end_date.isoformat(),
        )
        return normalized, rows
