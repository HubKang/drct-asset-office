from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from marcap import marcap_data
from marcap.marcap_utils import marcap_latest_available_date

from backend.app.collectors.prices.pykrx_price_collector import normalize_stock_code_for_pykrx


logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = ["Code", "Name", "Close", "Volume", "Amount", "Marcap", "Stocks", "Market", "MarketId", "Dept", "Rank"]


@dataclass
class MarcapMarketMetricRow:
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


class MarcapMarketMetricsCollector:
    @property
    def name(self) -> str:
        return "marcap_market_metrics_collector"

    @staticmethod
    def _to_float(value) -> float | None:
        if pd.isna(value):
            return None
        try:
            return float(value)
        except Exception:
            return None

    @staticmethod
    def _to_int(value) -> int | None:
        if pd.isna(value):
            return None
        try:
            return int(value)
        except Exception:
            return None

    @staticmethod
    def _fmt_trade_date(value) -> str:
        dt = pd.to_datetime(value)
        if isinstance(dt, pd.Timestamp):
            return dt.strftime("%Y-%m-%d")
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")
        return str(value)[:10]

    def collect_daily(self, trade_date: str) -> list[MarcapMarketMetricRow]:
        logger.info("Marcap market metrics fetch started: trade_date=%s", trade_date)
        df = marcap_data(trade_date)
        if df.empty:
            requested_dt = pd.to_datetime(trade_date).normalize()
            latest_dt = marcap_latest_available_date(requested_dt.year)
            if latest_dt is not None and latest_dt < requested_dt:
                raise LookupError(
                    "No marcap data for requested date "
                    f"{requested_dt.strftime('%Y-%m-%d')}. "
                    f"Latest available source date is {latest_dt.strftime('%Y-%m-%d')}."
                )
            raise LookupError(f"No marcap data for requested date {requested_dt.strftime('%Y-%m-%d')}.")

        missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
        if missing:
            raise ValueError(f"marcap required columns are missing: {missing}")

        rows: list[MarcapMarketMetricRow] = []
        for idx, row in df.iterrows():
            ticker = normalize_stock_code_for_pykrx(str(row.get("Code") or ""))
            if not ticker:
                continue
            rows.append(
                MarcapMarketMetricRow(
                    ticker=ticker,
                    name=None if pd.isna(row.get("Name")) else str(row.get("Name")),
                    trade_date=self._fmt_trade_date(idx),
                    market=None if pd.isna(row.get("Market")) else str(row.get("Market")),
                    close_price=self._to_float(row.get("Close")),
                    market_cap=self._to_int(row.get("Marcap")),
                    listed_shares=self._to_int(row.get("Stocks")),
                    trading_volume=self._to_int(row.get("Volume")),
                    trading_value=self._to_int(row.get("Amount")),
                    market_cap_rank=self._to_int(row.get("Rank")),
                )
            )

        logger.info("Marcap market metrics fetch completed: trade_date=%s rows=%s", trade_date, len(rows))
        return rows
