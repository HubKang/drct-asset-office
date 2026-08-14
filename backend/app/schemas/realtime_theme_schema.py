from __future__ import annotations

from pydantic import BaseModel, Field


class RealtimeThemeItem(BaseModel):
    theme_id: int
    theme_name: str
    rank: int
    avg_change_rate: float | None = None
    theme_strength: float | None = None
    linked_stock_count: int = 0
    valid_stock_count: int = 0


class RealtimeThemeTreemapResponse(BaseModel):
    trade_date: str
    snapshot_at: str | None = None
    theme_count: int = 0
    linked_stock_count: int = 0
    unique_stock_count: int = 0
    valid_stock_count: int = 0
    failed_stock_count: int = 0
    themes: list[RealtimeThemeItem] = Field(default_factory=list)


class RealtimeThemeRefreshResponse(RealtimeThemeTreemapResponse):
    success: bool = True
    price_api_call_count: int = 0
    kiwoom_fetch_ms: int = 0
    db_upsert_ms: int = 0
    theme_aggregation_ms: int = 0
    snapshot_response_ms: int = 0
    stock_fetch_min_ms: int | None = None
    stock_fetch_avg_ms: float | None = None
    stock_fetch_max_ms: int | None = None
    duration_ms: int = 0
    message: str


class RealtimeThemeStockItem(BaseModel):
    stock_id: int
    stock_code: str
    stock_name: str
    memo: str | None = None
    change_rate: float | None = None
    collected_at: str | None = None


class RealtimeThemeStocksResponse(BaseModel):
    theme_id: int
    theme_name: str
    theme_rank: int
    theme_change_rate: float | None = None
    trade_date: str
    snapshot_at: str | None = None
    linked_stock_count: int = 0
    valid_stock_count: int = 0
    stocks: list[RealtimeThemeStockItem] = Field(default_factory=list)
