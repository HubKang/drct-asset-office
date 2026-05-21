from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class KiwoomConditionItemIn(BaseModel):
    condition_seq: str
    condition_name: str


class KiwoomConditionSyncRequest(BaseModel):
    source: str = "kiwoom_rest"
    items: list[KiwoomConditionItemIn] = Field(default_factory=list)


class KiwoomConditionSyncResponse(BaseModel):
    success: bool
    inserted_count: int
    updated_count: int
    total_count: int


class KiwoomConditionItemOut(BaseModel):
    id: int
    condition_seq: str
    condition_name: str
    source: str
    is_active: int
    last_synced_at: str | None = None


class KiwoomConditionListResponse(BaseModel):
    items: list[KiwoomConditionItemOut]


class KiwoomConditionResultItemIn(BaseModel):
    stock_code: str
    stock_code_raw: str | None = None
    stock_name: str | None = None
    current_price: int | None = None
    change_rate: float | None = None
    intraday_change_rate: float | None = None
    trading_value: int | None = None
    volume: int | None = None
    source_api: str | None = None
    detected_at: str | None = None
    raw: dict[str, Any] | None = None


class KiwoomConditionResultSaveRequest(BaseModel):
    condition_name: str | None = None
    source: str = "kiwoom_rest"
    items: list[KiwoomConditionResultItemIn] = Field(default_factory=list)


class KiwoomConditionResultSaveResponse(BaseModel):
    success: bool
    saved_count: int
    skipped_count: int


class KiwoomConditionPreviewRequest(BaseModel):
    condition_name: str | None = None
    header_mode: str = "auth-only"
    login_mode: str = "message-token"
    search_type: str = "0"
    stex_tp: str = "K"


class KiwoomConditionResultItemOut(BaseModel):
    id: int
    condition_seq: str
    condition_name: str | None = None
    stock_code: str
    stock_code_raw: str | None = None
    stock_name: str | None = None
    current_price: int | None = None
    change_rate: float | None = None
    intraday_change_rate: float | None = None
    trading_value: int | None = None
    volume: int | None = None
    detected_at: str
    source_api: str | None = None
    estimated_trading_value: int | None = None


class KiwoomConditionResultListResponse(BaseModel):
    items: list[KiwoomConditionResultItemOut]


class KiwoomConditionPreviewResponse(BaseModel):
    success: bool
    condition_seq: str
    condition_name: str | None = None
    item_count: int
    items: list[KiwoomConditionResultItemOut] = Field(default_factory=list)
    error_message: str | None = None


class KiwoomMarketEventSaveRequest(BaseModel):
    condition_seq: str
    condition_name: str | None = None
    source: str = "kiwoom_rest"
    items: list[KiwoomConditionResultItemIn] = Field(default_factory=list)


class KiwoomMarketEventSaveResponse(BaseModel):
    success: bool
    saved_count: int
    updated_count: int
    unmatched_count: int
    unmatched_items: list[str] = Field(default_factory=list)


class KiwoomMarketEventItemOut(BaseModel):
    event_id: int
    trade_date: str
    stock_code: str | None = None
    stock_name: str | None = None
    market_type: str | None = None
    change_rate: float | None = None
    theme_status: str | None = None
    condition_seq: str | None = None
    condition_name: str | None = None
    user_memo: str | None = None
    detected_at: str | None = None
    updated_at: str | None = None


class KiwoomMarketEventListResponse(BaseModel):
    items: list[KiwoomMarketEventItemOut]


class KiwoomMarketEventPatchRequest(BaseModel):
    theme_status: str | None = None
    user_memo: str | None = None


class KiwoomMarketEventPatchResponse(BaseModel):
    success: bool
    item: KiwoomMarketEventItemOut


class KiwoomMarketEventDeleteResponse(BaseModel):
    success: bool
    event_id: int


class KiwoomMarketEventThemeLinkItemOut(BaseModel):
    link_id: int
    event_id: int
    market_theme_id: int
    theme_name: str
    link_reason: str | None = None
    user_memo: str | None = None
    is_primary: int = 0
    created_at: str | None = None
    updated_at: str | None = None


class KiwoomMarketEventThemeLinkListResponse(BaseModel):
    items: list[KiwoomMarketEventThemeLinkItemOut]


class KiwoomMarketEventThemeLinkAddRequest(BaseModel):
    market_theme_id: int
    link_reason: str | None = None
    user_memo: str | None = None
    is_primary: int = 0


class KiwoomMarketEventThemeLinkAddResponse(BaseModel):
    success: bool
    item: KiwoomMarketEventThemeLinkItemOut


class KiwoomMarketEventThemeLinkDeleteResponse(BaseModel):
    success: bool
    link_id: int


class DailyThemeFlowSummaryItem(BaseModel):
    market_theme_id: int
    theme_name: str
    event_count: int
    stock_count: int
    avg_change_rate: float | None = None
    max_change_rate: float | None = None
    estimated_trading_value_sum: int = 0
    representative_stocks: list[str] = Field(default_factory=list)


class DailyThemeFlowSummaryResponse(BaseModel):
    success: bool
    trade_date: str
    items: list[DailyThemeFlowSummaryItem] = Field(default_factory=list)


class DailyThemeFlowStockItem(BaseModel):
    event_id: int
    market_theme_id: int
    theme_name: str
    stock_code: str
    stock_name: str
    change_rate: float | None = None
    current_price: int | None = None
    volume: int | None = None
    estimated_trading_value: int | None = None
    condition_seq: str | None = None
    condition_name: str | None = None


class DailyThemeFlowStocksResponse(BaseModel):
    success: bool
    trade_date: str
    market_theme_id: int
    theme_name: str | None = None
    items: list[DailyThemeFlowStockItem] = Field(default_factory=list)
