from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

UsExchange = Literal["NASDAQ", "NYSE", "NYSE_AMERICAN", "OTHER"]
UsStockType = Literal["COMMON", "ETF", "OTHER"]
UsHistoricalPriceStatus = Literal["NOT_COLLECTED", "COMPLETE", "PARTIAL", "ERROR"]


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


class UsStockCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    name: str | None = Field(default=None, max_length=200)
    name_ko: str | None = Field(default=None, max_length=200)
    exchange: UsExchange
    stock_type: UsStockType = "COMMON"
    naver_code: str | None = Field(default=None, max_length=50)
    is_active: int = Field(default=1, ge=0, le=1)

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, value: str) -> str:
        symbol = value.strip().upper()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]{0,19}", symbol):
            raise ValueError("Ticker는 영문, 숫자, 점, 하이픈만 사용할 수 있습니다.")
        return symbol

    @field_validator("name", "name_ko", "naver_code")
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class UsStockUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    name_ko: str | None = Field(default=None, max_length=200)
    exchange: UsExchange | None = None
    stock_type: UsStockType | None = None
    naver_code: str | None = Field(default=None, max_length=50)
    is_active: int | None = Field(default=None, ge=0, le=1)

    @field_validator("name", "name_ko", "naver_code")
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        return _clean_optional(value)


class UsStockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    name: str | None
    name_ko: str | None
    exchange: str
    stock_type: str
    naver_code: str | None
    is_active: int
    last_synced_at: str | None
    historical_price_status: Literal["NOT_COLLECTED", "COMPLETE", "PARTIAL", "ERROR"] = "NOT_COLLECTED"
    historical_price_completed_at: str | None = None
    historical_price_row_count: int = 0
    created_at: str
    updated_at: str
    latest_price_date: str | None = None
    latest_close: float | None = None
    latest_change_rate: float | None = None
    price_status: Literal["NOT_COLLECTED", "COMPLETE", "PARTIAL", "ERROR"] = "NOT_COLLECTED"


class UsStockListResponse(BaseModel):
    items: list[UsStockResponse]
    total: int
    page: int
    page_size: int


class UsStockSummaryResponse(BaseModel):
    total: int
    active: int
    common: int
    etf: int
    price_complete: int = 0
    price_not_collected: int = 0
    price_partial: int = 0
    price_error: int = 0
    latest_price_date: str | None = None


class UsStockDeleteImpactResponse(BaseModel):
    stock_id: int
    symbol: str
    price_row_count: int
    theme_link_count: int
    affected_theme_count: int


class UsStockDeleteResponse(BaseModel):
    deleted: bool
    stock_id: int
    symbol: str
    deleted_price_count: int
    deleted_theme_link_count: int
    invalidated_theme_return_count: int
    recalculated_theme_count: int
    message: str


class UsStockBulkRequest(BaseModel):
    tickers: list[str] = Field(min_length=1, max_length=200)
    exchange: UsExchange
    stock_type: UsStockType = "COMMON"
    is_active: int = Field(default=1, ge=0, le=1)


class UsStockBulkPreviewItem(BaseModel):
    symbol: str
    exchange: str
    stock_type: str
    status: Literal["NEW", "EXISTING", "DUPLICATE", "INVALID"]
    reason: str | None = None


class UsStockBulkPreviewResponse(BaseModel):
    items: list[UsStockBulkPreviewItem]
    new_count: int
    existing_count: int
    invalid_count: int


class UsStockBulkCreateResponse(BaseModel):
    created_count: int
    skipped_count: int
    items: list[UsStockResponse]


class UsPriceCollectionRequest(BaseModel):
    mode: Literal["INCREMENTAL", "MISSING", "SELECTED", "ALL_ACTIVE", "BACKFILL"] = "INCREMENTAL"
    stock_ids: list[int] | None = Field(default=None, max_length=200)
    trading_days: int = Field(default=260, ge=2, le=1000)

    @model_validator(mode="after")
    def validate_selected_ids(self):
        if self.mode == "SELECTED" and not self.stock_ids:
            raise ValueError("선택 종목 과거가격 수집에는 stock_ids가 필요합니다.")
        return self


class UsPriceCollectionFailure(BaseModel):
    stock_id: int
    symbol: str
    reason: str


class UsPriceCollectionResponse(BaseModel):
    mode: Literal["INCREMENTAL", "MISSING", "SELECTED", "ALL_ACTIVE", "BACKFILL"]
    requested_stock_count: int
    success_stock_count: int
    failed_stock_count: int
    inserted_count: int
    updated_count: int
    affected_date_from: str | None
    affected_date_to: str | None
    recalculated_theme_count: int = 0
    latest_price_date: str | None = None
    failures: list[UsPriceCollectionFailure]
    message: str


class UsStockDailyPriceResponse(BaseModel):
    trade_date: str
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: int


class UsStockPriceListResponse(BaseModel):
    stock_id: int
    symbol: str
    items: list[UsStockDailyPriceResponse]
