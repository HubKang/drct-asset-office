from __future__ import annotations

from pydantic import BaseModel


class MarketMetricsDailyCollectRequest(BaseModel):
    trade_date: str
    source: str = "marcap"


class MarketMetricsDailyCollectResponse(BaseModel):
    trade_date: str
    source: str
    requested_count: int
    matched_count: int
    saved_count: int
    skipped_count: int
    failed_count: int
    message: str


class StockMarketMetricLatestResponse(BaseModel):
    stock_id: int
    stock_code: str
    stock_name: str
    source: str
    trade_date: str
    market: str | None = None
    close_price: float | None = None
    market_cap: int | None = None
    listed_shares: int | None = None
    trading_volume: int | None = None
    trading_value: int | None = None
    market_cap_rank: int | None = None
    trading_value_rank: int | None = None
    market_trading_value_rank: int | None = None
    trading_value_percentile: float | None = None
    market_trading_value_percentile: float | None = None


class StockMarketMetricSummaryResponse(BaseModel):
    stock_id: int
    stock_code: str
    stock_name: str
    source: str
    latest_market_metrics_date: str
    latest_price_trade_date: str | None = None
    is_stale: bool
    stale_days: int | None = None
    staleness_level: str
    market: str | None = None
    trading_value: int | None = None
    market_cap: int | None = None
    listed_shares: int | None = None
    trading_volume: int | None = None
    market_cap_rank: int | None = None
    trading_value_rank: int | None = None
    market_trading_value_rank: int | None = None
    trading_value_percentile: float | None = None
    market_trading_value_percentile: float | None = None
    data_note: str
