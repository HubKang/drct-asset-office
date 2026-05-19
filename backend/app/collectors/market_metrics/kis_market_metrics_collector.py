from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import requests

from backend.app.collectors.prices.kis.kis_auth_client import KisAuthClient


@dataclass
class KisMarketMetricRow:
    trade_date: str
    close_price: float | None
    market_cap: int | None
    listed_shares: int | None
    trading_volume: int | None
    trading_value: int | None
    market: str | None
    source: str = "kis_api"


class KisMarketMetricsCollector:
    def __init__(self) -> None:
        self.auth_client = KisAuthClient()
        self.base_url = self.auth_client.base_url
        self.timeout = self.auth_client.timeout

    @property
    def name(self) -> str:
        return "kis_market_metrics_collector"

    @staticmethod
    def _to_float(value: str | int | float | None) -> float | None:
        if value in (None, "", "-"):
            return None
        try:
            return float(str(value).replace(",", ""))
        except ValueError:
            return None

    @staticmethod
    def _to_int(value: str | int | float | None) -> int | None:
        if value in (None, "", "-"):
            return None
        try:
            return int(float(str(value).replace(",", "")))
        except ValueError:
            return None

    @staticmethod
    def _to_trade_date(value: str | None) -> str:
        raw = (value or "").strip()
        if len(raw) == 8 and raw.isdigit():
            return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
        return date.today().isoformat()

    @staticmethod
    def _to_market(code: str | None) -> str | None:
        if code == "300":
            return "KOSPI"
        if code == "301":
            return "KOSDAQ"
        return None

    def collect_latest(self, stock_code: str) -> KisMarketMetricRow:
        try:
            token = self.auth_client.get_access_token()
        except ValueError as exc:
            msg = str(exc).lower()
            if "설정" in str(exc) or "app_key" in msg or "app_secret" in msg:
                raise RuntimeError("env_missing") from exc
            if "token" in msg or "인증" in str(exc):
                raise RuntimeError("auth_failed") from exc
            raise RuntimeError("unknown_error") from exc
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
        headers = {
            "authorization": f"Bearer {token}",
            "appkey": self.auth_client.app_key,
            "appsecret": self.auth_client.app_secret,
            "tr_id": "FHKST01010100",
            "custtype": "P",
        }
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": stock_code,
        }
        try:
            response = requests.get(url, headers=headers, params=params, timeout=self.timeout)
        except requests.RequestException as exc:
            raise RuntimeError("network_error") from exc

        if response.status_code == 401:
            raise RuntimeError("auth_failed")
        if response.status_code == 403:
            raise RuntimeError("api_permission_denied")
        if response.status_code == 429:
            raise RuntimeError("rate_limited")
        if response.status_code >= 400:
            raise RuntimeError("unknown_error")

        payload = response.json()
        rt_cd = str(payload.get("rt_cd") or "")
        if rt_cd not in {"0", ""}:
            msg_cd = str(payload.get("msg_cd") or "")
            msg1 = str(payload.get("msg1") or "").lower()
            if "token" in msg1 or msg_cd in {"EGW00121", "OPSQ0002"}:
                raise RuntimeError("token_expired")
            if "no data" in msg1 or "조회된 data가 없습니다" in msg1:
                raise RuntimeError("no_data")
            raise RuntimeError("unknown_error")

        output = payload.get("output") or {}
        if not isinstance(output, dict) or not output:
            raise RuntimeError("no_data")

        raw_market_cap = self._to_int(output.get("hts_avls"))
        # KIS hts_avls is in hundred-million KRW units(억원) for domestic quote.
        # Normalize to KRW for storage consistency with other sources.
        market_cap_krw = None if raw_market_cap is None else int(raw_market_cap) * 100_000_000

        return KisMarketMetricRow(
            trade_date=self._to_trade_date(str(output.get("stck_bsop_date") or "")),
            close_price=self._to_float(output.get("stck_prpr")),
            market_cap=market_cap_krw,
            listed_shares=self._to_int(output.get("lstn_stcn")),
            trading_volume=self._to_int(output.get("acml_vol")),
            trading_value=self._to_int(output.get("acml_tr_pbmn")),
            market=self._to_market(str(output.get("mrkt_ctg") or "")),
            source="kis_api",
        )
