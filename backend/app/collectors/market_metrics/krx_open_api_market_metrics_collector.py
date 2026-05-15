from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd
import requests

from backend.app.collectors.prices.pykrx_price_collector import normalize_stock_code_for_pykrx
from backend.app.core.config import (
    KRX_OPEN_API_AUTH_KEY,
    KRX_OPEN_API_BASE_URL,
    KRX_OPEN_API_TIMEOUT_SECONDS,
)


logger = logging.getLogger(__name__)

KOSPI_ENDPOINT = "sto/stk_bydd_trd"
KOSDAQ_ENDPOINT = "sto/ksq_bydd_trd"
REQUIRED_COLUMNS = ["ISU_NM", "TDD_CLSPRC", "ACC_TRDVOL", "ACC_TRDVAL", "MKTCAP", "LIST_SHRS"]


@dataclass
class KRXOpenAPIMarketMetricRow:
    ticker: str
    name: str | None
    trade_date: str
    market: str | None
    close_price: float | None
    market_cap: int | None
    listed_shares: int | None
    trading_volume: int | None
    trading_value: int | None
    market_cap_rank: int | None


class KRXOpenAPIMarketMetricsCollector:
    AUTHORIZATION_FAILED_MESSAGE = (
        "KRX Open API authorization failed. Check whether this API key is approved for the requested "
        "KRX daily trading information services."
    )

    @property
    def name(self) -> str:
        return "krx_open_api_market_metrics_collector"

    @staticmethod
    def _clean_number(value) -> float | int | None:
        if value is None or pd.isna(value):
            return None
        text = str(value).strip().replace(",", "")
        if text == "":
            return None
        try:
            number = float(text)
        except Exception:
            return None
        if number.is_integer():
            return int(number)
        return number

    @staticmethod
    def _to_float(value) -> float | None:
        cleaned = KRXOpenAPIMarketMetricsCollector._clean_number(value)
        if cleaned is None:
            return None
        return float(cleaned)

    @staticmethod
    def _to_int(value) -> int | None:
        cleaned = KRXOpenAPIMarketMetricsCollector._clean_number(value)
        if cleaned is None:
            return None
        try:
            return int(cleaned)
        except Exception:
            return None

    @staticmethod
    def _extract_rows(payload: dict) -> list[dict]:
        rows = payload.get("OutBlock_1")
        if isinstance(rows, list):
            return rows
        return []

    def _request_market(self, endpoint: str, trade_date: str, market_label: str) -> pd.DataFrame:
        if not KRX_OPEN_API_AUTH_KEY:
            raise RuntimeError("KRX_OPEN_API_AUTH_KEY is not configured.")

        url = f"{KRX_OPEN_API_BASE_URL.rstrip('/')}/{endpoint}"
        headers = {
            "AUTH_KEY": KRX_OPEN_API_AUTH_KEY,
            "Accept": "application/json",
        }
        params = {"basDd": trade_date.replace("-", "")}
        session = requests.Session()
        session.trust_env = False
        response = session.get(url, headers=headers, params=params, timeout=KRX_OPEN_API_TIMEOUT_SECONDS)

        content_type = response.headers.get("Content-Type", "")
        if response.status_code == 401:
            raise RuntimeError(self.AUTHORIZATION_FAILED_MESSAGE)
        if response.status_code != 200:
            detail = response.text[:300]
            raise RuntimeError(f"KRX Open API request failed for {market_label}: {response.status_code} {detail}")
        if "json" not in content_type.lower():
            raise RuntimeError(f"KRX Open API returned non-JSON response for {market_label}: {content_type}")

        payload = response.json()
        if isinstance(payload, dict) and payload.get("respCode") not in (None, "000", "00"):
            raise RuntimeError(
                f"KRX Open API error for {market_label}: {payload.get('respCode')} {payload.get('respMsg', '')}".strip()
            )

        rows = self._extract_rows(payload)
        df = pd.DataFrame(rows)
        if df.empty:
            return df

        missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
        if missing:
            raise ValueError(f"KRX Open API required columns are missing for {market_label}: {missing}")

        df["MARKET_LABEL"] = market_label
        return df

    def collect_daily(self, trade_date: str) -> list[KRXOpenAPIMarketMetricRow]:
        logger.info("KRX Open API market metrics fetch started: trade_date=%s", trade_date)
        frames = [
            self._request_market(KOSPI_ENDPOINT, trade_date, "KOSPI"),
            self._request_market(KOSDAQ_ENDPOINT, trade_date, "KOSDAQ"),
        ]
        df = pd.concat([frame for frame in frames if not frame.empty], ignore_index=True) if any(
            not frame.empty for frame in frames
        ) else pd.DataFrame()

        if df.empty:
            raise LookupError(f"No KRX Open API market metrics data for requested date {trade_date}.")

        rows: list[KRXOpenAPIMarketMetricRow] = []
        for _, row in df.iterrows():
            raw_code = row.get("ISU_SRT_CD") or row.get("ISU_CD")
            ticker = normalize_stock_code_for_pykrx(str(raw_code or ""))
            if not ticker:
                continue
            rows.append(
                KRXOpenAPIMarketMetricRow(
                    ticker=ticker,
                    name=None if pd.isna(row.get("ISU_NM")) else str(row.get("ISU_NM")),
                    trade_date=trade_date,
                    market=None if pd.isna(row.get("MKT_NM")) else str(row.get("MKT_NM")) if row.get("MKT_NM") else str(row.get("MARKET_LABEL")),
                    close_price=self._to_float(row.get("TDD_CLSPRC")),
                    market_cap=self._to_int(row.get("MKTCAP")),
                    listed_shares=self._to_int(row.get("LIST_SHRS")),
                    trading_volume=self._to_int(row.get("ACC_TRDVOL")),
                    trading_value=self._to_int(row.get("ACC_TRDVAL")),
                    market_cap_rank=None,
                )
            )

        logger.info("KRX Open API market metrics fetch completed: trade_date=%s rows=%s", trade_date, len(rows))
        return rows
