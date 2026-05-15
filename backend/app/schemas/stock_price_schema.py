from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StockDailyPriceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_id: int
    trade_date: str
    open_price: float | None = None
    high_price: float | None = None
    low_price: float | None = None
    close_price: float | None = None
    change_price: float | None = None
    change_rate: float | None = None
    volume: int | None = None
    trading_value: int | None = None
    ma5: float | None = None
    ma10: float | None = None
    ma20: float | None = None
    ma60: float | None = None
    ma120: float | None = None
    ma240: float | None = None
    source: str | None = None
    created_at: str
    updated_at: str


class StockDailyPriceListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_id: int
    stock_code: str
    stock_name: str
    trade_date: str
    open_price: float | None = None
    high_price: float | None = None
    low_price: float | None = None
    close_price: float | None = None
    change_price: float | None = None
    change_rate: float | None = None
    volume: int | None = None
    trading_value: int | None = None
    ma5: float | None = None
    ma10: float | None = None
    ma20: float | None = None
    ma60: float | None = None
    ma120: float | None = None
    ma240: float | None = None
    source: str | None = None
    created_at: str
    updated_at: str


class StockPriceSummaryItem(BaseModel):
    stock_id: int
    stock_code: str
    stock_name: str
    market: str | None = None
    security_type: str | None = None
    price_count: int
    min_trade_date: str | None = None
    max_trade_date: str | None = None
    latest_close_price: float | None = None
    latest_volume: int | None = None
    latest_trading_value: int | None = None
    latest_ma5: float | None = None
    latest_ma20: float | None = None
    latest_ma60: float | None = None
    latest_ma120: float | None = None
    latest_ma240: float | None = None
    source: str | None = None


class StockPriceSummaryResponse(BaseModel):
    items: list[StockPriceSummaryItem] = Field(default_factory=list)
    limit: int
    offset: int


class StockPriceFactSummaryResponse(BaseModel):
    stock_id: int
    stock_code: str
    stock_name: str
    source: str
    price_count: int
    min_trade_date: str | None = None
    max_trade_date: str | None = None
    latest_trade_date: str | None = None
    latest_close_price: float | None = None
    latest_ma5: float | None = None
    latest_ma20: float | None = None
    latest_ma60: float | None = None
    recent_5d_change_rate: float | None = None
    avg_volume_20d: float | None = None
    high_52w: float | None = None
    high_52w_date: str | None = None
    price_position_vs_52w_high: float | None = None


class StockDailyPriceListResponse(BaseModel):
    stock_id: int
    stock_code: str
    stock_name: str
    items: list[StockDailyPriceListItem] = Field(default_factory=list)
    limit: int
    offset: int


class SelectedStockPriceCollectRequest(BaseModel):
    stock_ids: list[int] = Field(default_factory=list)
    period_years: int = 2
    source: str = "pykrx"


class StockPriceCollectItemResult(BaseModel):
    stock_id: int
    stock_code: str
    normalized_stock_code: str | None = None
    stock_name: str
    status: str
    mode: str | None = None
    from_date: str | None = None
    to_date: str | None = None
    collected_count: int = 0
    saved_count: int = 0
    source: str | None = None
    message: str | None = None


class StockPriceCollectResult(BaseModel):
    requested_count: int
    success_count: int
    failed_count: int
    skipped_count: int = 0
    saved_count: int
    source: str | None = None
    message: str
    results: list[StockPriceCollectItemResult] = Field(default_factory=list)
