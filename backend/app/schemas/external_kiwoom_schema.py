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


class KiwoomConditionRefreshResponse(BaseModel):
    success: bool
    source: str
    api_id: str
    return_code: str | None = None
    return_msg: str | None = None
    condition_count: int
    inserted: int
    updated: int
    total: int
    top_level_keys: list[str] = Field(default_factory=list)
    sample_conditions: list[dict[str, str]] = Field(default_factory=list)
    message: str | None = None


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
    source: str | None = None
    api_id: str | None = None
    condition_seq: str
    condition_name: str | None = None
    requested_condition_seq: str | None = None
    requested_condition_name: str | None = None
    resolved_condition_seq: str | None = None
    resolved_condition_name: str | None = None
    return_code: str | None = None
    return_msg: str | None = None
    item_count: int
    items: list[KiwoomConditionResultItemOut] = Field(default_factory=list)
    parsing_error: bool = False
    debug: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None


class KiwoomMarketEventSaveRequest(BaseModel):
    condition_seq: str
    condition_name: str | None = None
    detected_date: str | None = None
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
    detection_source: str | None = None
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


class ThemeStockSyncResult(BaseModel):
    status: str
    reason: str | None = None
    mapping_id: int | None = None


class ThemeStockSyncSummary(BaseModel):
    created: int = 0
    reactivated: int = 0
    deactivated: int = 0
    skipped: int = 0
    failed: int = 0


class KiwoomMarketEventDeleteResponse(BaseModel):
    success: bool
    event_id: int
    theme_stock_sync: ThemeStockSyncSummary | None = None


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
    theme_stock_sync: ThemeStockSyncResult | None = None


class KiwoomMarketEventThemeLinkDeleteResponse(BaseModel):
    success: bool
    link_id: int
    theme_stock_sync: ThemeStockSyncResult | None = None


class MarketThemeReturnRefreshRequest(BaseModel):
    scope: str = "all_active"
    theme_ids: list[int] = Field(default_factory=list)


class MarketThemeReturnRefreshItem(BaseModel):
    theme_id: int
    theme_name: str
    return_date: str
    avg_change_rate: float | None = None
    stock_count: int = 0
    success_stock_count: int = 0
    failed_stock_count: int = 0
    total_trading_value_100m: float | None = None
    save_action: str = "skipped"


class MarketThemeReturnRefreshResponse(BaseModel):
    success: bool
    return_date: str
    refreshed_at: str
    theme_count: int = 0
    stock_count: int = 0
    success_stock_count: int = 0
    failed_stock_count: int = 0
    inserted_count: int = 0
    updated_count: int = 0
    items: list[MarketThemeReturnRefreshItem] = Field(default_factory=list)
    message: str | None = None


class MarketThemeReturnStockItem(BaseModel):
    stock_id: int
    stock_code: str | None = None
    stock_name: str
    trading_value_100m: float | None = None
    change_rate: float | None = None
    current_price: int | None = None
    data_status: str = "missing"
    error_message: str | None = None


class MarketThemeLatestReturnResponse(BaseModel):
    theme_id: int
    theme_name: str
    theme_group_name: str | None = None
    return_date: str | None = None
    avg_change_rate: float | None = None
    snapshot_at: str | None = None
    stock_count: int = 0
    success_stock_count: int = 0
    failed_stock_count: int = 0
    rising_stock_count: int = 0
    falling_stock_count: int = 0
    flat_stock_count: int = 0
    total_trading_value_100m: float | None = None
    stocks: list[MarketThemeReturnStockItem] = Field(default_factory=list)


class MarketThemeMonthlyReturnDailyItem(BaseModel):
    return_date: str
    avg_change_rate: float | None = None
    total_trading_value_100m: float | None = None
    rising_stock_count: int = 0
    falling_stock_count: int = 0
    flat_stock_count: int = 0


class MarketThemeMonthlyReturnThemeItem(BaseModel):
    theme_id: int
    theme_name: str
    theme_group_id: int | None = None
    theme_group_name: str | None = None
    monthly_compound_return: float | None = None
    monthly_sum_return: float | None = None
    period_compound_return: float | None = None
    period_sum_return: float | None = None
    total_trading_value_100m: float | None = None
    rising_days: int = 0
    falling_days: int = 0
    flat_days: int = 0
    data_days: int = 0
    daily_returns: list[MarketThemeMonthlyReturnDailyItem] = Field(default_factory=list)


class MarketThemeMonthlyReturnSummaryTopItem(BaseModel):
    theme_id: int
    theme_name: str
    monthly_compound_return: float | None = None
    period_compound_return: float | None = None
    total_trading_value_100m: float | None = None
    continuous_rising_days: int | None = None


class MarketThemeMonthlyReturnSummary(BaseModel):
    top_rising_theme: MarketThemeMonthlyReturnSummaryTopItem | None = None
    top_falling_theme: MarketThemeMonthlyReturnSummaryTopItem | None = None
    top_trading_value_theme: MarketThemeMonthlyReturnSummaryTopItem | None = None
    rising_day_theme: MarketThemeMonthlyReturnSummaryTopItem | None = None
    top_continuous_rising_theme: MarketThemeMonthlyReturnSummaryTopItem | None = None


class MarketThemeMonthlyReturnResponse(BaseModel):
    month: str | None = None
    end_date: str | None = None
    days: int | None = None
    active_only: bool = True
    display_start_date: str
    display_end_date: str
    themes: list[MarketThemeMonthlyReturnThemeItem] = Field(default_factory=list)
    summary: MarketThemeMonthlyReturnSummary

class DailyThemeFlowSummaryItem(BaseModel):
    market_theme_id: int
    theme_name: str
    event_count: int
    stock_count: int
    avg_change_rate: float | None = None
    max_change_rate: float | None = None
    estimated_trading_value_sum: int = 0
    representative_stocks: list[str] = Field(default_factory=list)
    auto_rank: int | None = None
    manual_rank: int | None = None
    final_rank: int | None = None
    rank_score: float = 0
    rank_basis: str = "auto"


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
    user_memo: str | None = None


class DailyThemeFlowStocksResponse(BaseModel):
    success: bool
    trade_date: str
    market_theme_id: int
    theme_name: str | None = None
    items: list[DailyThemeFlowStockItem] = Field(default_factory=list)


class MonthlyThemeFlowStockItem(BaseModel):
    stock_id: int | None = None
    stock_code: str | None = None
    stock_name: str


class MonthlyThemeFlowMemoItem(BaseModel):
    theme_id: int | None = None
    theme_name: str
    stock_code: str | None = None
    stock_name: str
    memo: str


class MonthlyThemeFlowCalendarThemeItem(BaseModel):
    rank: int
    theme_group_id: int | None = None
    theme_group_name: str = "미지정 테마그룹"
    market_theme_id: int
    theme_name: str
    stock_count: int
    event_count: int
    avg_change_rate: float | None = None
    max_change_rate: float | None = None
    estimated_trading_value_sum: int = 0
    auto_rank: int | None = None
    manual_rank: int | None = None
    final_rank: int | None = None
    rank_score: float = 0
    rank_basis: str = "auto"
    stocks: list[MonthlyThemeFlowStockItem] = Field(default_factory=list)


class MonthlyThemeFlowCalendarDayItem(BaseModel):
    trade_date: str
    event_count: int = 0
    related_stock_count: int = 0
    themes: list[MonthlyThemeFlowCalendarThemeItem] = Field(default_factory=list)
    memo_items: list[MonthlyThemeFlowMemoItem] = Field(default_factory=list)


class MonthlyThemeFlowCalendarResponse(BaseModel):
    success: bool
    month: str
    start_date: str
    end_date: str
    days: list[MonthlyThemeFlowCalendarDayItem] = Field(default_factory=list)


class MonthlyThemeFlowTrendPoint(BaseModel):
    trade_date: str
    value: int
    daily_score: int = 0
    final_rank: int | None = None
    rank_basis: str = "auto"
    stock_count: int
    event_count: int
    avg_change_rate: float | None = None
    max_change_rate: float | None = None
    estimated_trading_value_sum: int = 0


class MonthlyThemeFlowTrendTheme(BaseModel):
    market_theme_id: int
    theme_name: str
    view_mode: str = "THEME"
    theme_group_id: int | None = None
    theme_group_name: str | None = None
    child_theme_count: int = 0
    top_child_themes: list[str] = Field(default_factory=list)
    related_stocks: list[str] = Field(default_factory=list)
    series: list[MonthlyThemeFlowTrendPoint] = Field(default_factory=list)


class MonthlyThemeFlowTrendResponse(BaseModel):
    success: bool
    month: str
    start_date: str
    end_date: str
    themes: list[MonthlyThemeFlowTrendTheme] = Field(default_factory=list)


class DailyThemeRankUpdateItem(BaseModel):
    market_theme_id: int
    manual_rank: int | None = None
    user_memo: str | None = None


class DailyThemeRanksUpdateRequest(BaseModel):
    trade_date: str
    items: list[DailyThemeRankUpdateItem] = Field(default_factory=list)


class DailyThemeRanksUpdateResponse(BaseModel):
    success: bool
    trade_date: str
    updated_count: int
    items: list[DailyThemeFlowSummaryItem] = Field(default_factory=list)
