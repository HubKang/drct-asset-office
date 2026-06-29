from __future__ import annotations

from pydantic import BaseModel, Field


class MarketIndexItem(BaseModel):
    id: int
    index_code: str
    index_name: str
    category: str
    market: str
    currency: str
    provider: str
    provider_symbol: str | None = None
    description: str | None = None
    is_active: bool
    display_order: int
    last_collected_date: str | None = None
    collection_status: str
    error_message: str | None = None
    latest_price_date: str | None = None
    latest_close_price: float | None = None
    latest_close: float | None = None
    latest_volume: int | None = None
    latest_trading_value: int | None = None
    recent_5d_return: float | None = None
    recent_20d_return: float | None = None
    recent_5d_return_pct: float | None = None
    recent_20d_return_pct: float | None = None


class MarketIndexListResponse(BaseModel):
    items: list[MarketIndexItem] = Field(default_factory=list)


class MarketIndexDailyPriceItem(BaseModel):
    id: int | None = None
    index_code: str
    price_date: str
    open_price: float | None = None
    high_price: float | None = None
    low_price: float | None = None
    close_price: float | None = None
    volume: int | None = None
    trading_value: int | None = None
    change_rate: float | None = None
    ma5: float | None = None
    ma20: float | None = None
    ma60: float | None = None
    ma120: float | None = None
    source_provider: str | None = None


class MarketIndexDailyPriceListResponse(BaseModel):
    index_code: str
    index_name: str | None = None
    items: list[MarketIndexDailyPriceItem] = Field(default_factory=list)


class MarketIndexCollectRequest(BaseModel):
    index_codes: list[str] | None = None
    start_date: str | None = None
    end_date: str | None = None


class MarketIndexCollectItemResult(BaseModel):
    index_code: str
    index_name: str | None = None
    status: str
    collected_count: int = 0
    saved_count: int = 0
    from_date: str | None = None
    to_date: str | None = None
    message: str | None = None
    last_collected_date: str | None = None
    error_message: str | None = None


class MarketIndexCollectResponse(BaseModel):
    requested_count: int
    success_count: int
    failed_count: int
    saved_count: int
    message: str
    results: list[MarketIndexCollectItemResult] = Field(default_factory=list)


class MarketIndexCompareSeries(BaseModel):
    index_code: str
    index_name: str | None = None
    points: list[dict] = Field(default_factory=list)


class MarketIndexCompareResponse(BaseModel):
    normalize: bool = True
    start_date: str | None = None
    end_date: str | None = None
    series: list[MarketIndexCompareSeries] = Field(default_factory=list)

