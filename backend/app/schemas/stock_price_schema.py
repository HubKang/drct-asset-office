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


class SelectedStockPriceCollectRequest(BaseModel):
    stock_ids: list[int] = Field(default_factory=list)
    period_years: int = 2
    source: str = "mock"


class StockPriceUpdateRequest(BaseModel):
    stock_ids: list[int] = Field(default_factory=list)
    source: str = "mock"


class StockPriceCollectItemResult(BaseModel):
    stock_id: int
    stock_code: str
    stock_name: str
    status: str
    saved_count: int = 0
    message: str | None = None


class StockPriceCollectResult(BaseModel):
    requested_count: int
    success_count: int
    failed_count: int
    saved_count: int
    message: str
    results: list[StockPriceCollectItemResult] = Field(default_factory=list)
