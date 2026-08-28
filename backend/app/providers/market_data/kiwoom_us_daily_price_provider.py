from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from backend.app.clients.kiwoom.kiwoom_rest_client import KiwoomRestClient
from backend.app.providers.market_data.us_daily_price_provider import (
    UsDailyPrice,
    UsDailyPriceFetchResult,
    UsHistoricalPricePartialError,
)


KIWOOM_US_EXCHANGE_CODES = {
    "NASDAQ": "ND",
    "NYSE": "NY",
    "NYSE_AMERICAN": "NA",
}


class KiwoomUsDailyPriceProvider:
    """Transient parser for Kiwoom usa06012; raw provider payloads are never persisted."""

    API_ID = "usa06012"
    PATH = "/api/us/chart"

    def __init__(self, client: KiwoomRestClient | None = None) -> None:
        self.client = client or KiwoomRestClient()

    @staticmethod
    def exchange_code(exchange: str) -> str:
        try:
            return KIWOOM_US_EXCHANGE_CODES[exchange]
        except KeyError as exc:
            raise ValueError(f"Kiwoom 수집을 지원하지 않는 거래소입니다: {exchange}") from exc

    @staticmethod
    def _decimal(value: Any) -> float:
        cleaned = str(value or "").strip().replace(",", "")
        if not cleaned:
            raise ValueError("price_missing")
        try:
            return float(Decimal(cleaned))
        except InvalidOperation as exc:
            raise ValueError("price_invalid") from exc

    @staticmethod
    def _integer(value: Any) -> int:
        cleaned = str(value or "0").strip().replace(",", "")
        try:
            return max(int(Decimal(cleaned or "0")), 0)
        except InvalidOperation as exc:
            raise ValueError("volume_invalid") from exc

    @classmethod
    def _parse_row(cls, row: dict[str, Any]) -> UsDailyPrice | None:
        raw_date = str(row.get("dt") or "").strip()
        if len(raw_date) != 8 or not raw_date.isdigit():
            return None
        trade_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
        try:
            date.fromisoformat(trade_date)
            close = cls._decimal(row.get("cur_prc"))
            open_price = cls._decimal(row.get("open_pric"))
            high = cls._decimal(row.get("high_pric"))
            low = cls._decimal(row.get("low_pric"))
            volume = cls._integer(row.get("acc_trde_qty"))
        except (ValueError, TypeError):
            return None
        if min(close, open_price, high, low) <= 0:
            return None
        return UsDailyPrice(trade_date, open_price, high, low, close, volume)

    def fetch_history(self, *, symbol: str, exchange: str, start_date: str, trading_days: int) -> UsDailyPriceFetchResult:
        body = {
            "stex_tp": self.exchange_code(exchange),
            "stk_cd": symbol,
            "strt_dt": start_date.replace("-", ""),
            "upd_stkpc_tp": "1",
            "exrt_appl_tp": "0",
        }
        rows_by_date: dict[str, UsDailyPrice] = {}
        cont_yn: str | None = None
        next_key: str | None = None
        page_count = 0
        history_exhausted = False
        while len(rows_by_date) < trading_days and page_count < 30:
            try:
                response = self.client.post_json(
                    self.PATH,
                    api_id=self.API_ID,
                    body=body,
                    cont_yn=cont_yn,
                    next_key=next_key,
                )
            except Exception as exc:
                if rows_by_date:
                    raise UsHistoricalPricePartialError(sorted(rows_by_date.values(), key=lambda item: item.trade_date), str(exc)) from exc
                raise
            result_list = response.json_body.get("result_list")
            if not isinstance(result_list, list):
                result_list = []
            for raw in result_list:
                if not isinstance(raw, dict):
                    continue
                parsed = self._parse_row(raw)
                if parsed:
                    rows_by_date[parsed.trade_date] = parsed
            page_count += 1
            if str(response.cont_yn).upper() != "Y" or not response.next_key:
                history_exhausted = True
                break
            cont_yn, next_key = "Y", response.next_key
        prices = sorted(rows_by_date.values(), key=lambda item: item.trade_date)[-trading_days:]
        return UsDailyPriceFetchResult(prices=prices, history_exhausted=history_exhausted)

    def fetch(self, *, symbol: str, exchange: str, start_date: str, trading_days: int) -> list[UsDailyPrice]:
        """Compatibility wrapper for callers that only need parsed price rows."""
        return self.fetch_history(symbol=symbol, exchange=exchange, start_date=start_date, trading_days=trading_days).prices
