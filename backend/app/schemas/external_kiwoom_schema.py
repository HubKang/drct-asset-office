from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field
from backend.app.schemas.market_theme_stock_schema import StockDailyFlowSummary, ThemeDailyFlowSummary


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


class KiwoomMarketEventExistingThemeOut(BaseModel):
    theme_id: int
    theme_name: str
    theme_group_id: int | None = None
    theme_group_name: str | None = None
    is_active: int = 1


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
    existing_themes: list[KiwoomMarketEventExistingThemeOut] = Field(default_factory=list)


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
    mode: Literal["FULL", "PILOT"] = "FULL"
    pilot_stock_ids: list[int] = Field(default_factory=list)
    pilot_stock_codes: list[str] = Field(default_factory=list)
    max_stocks: int | None = Field(default=None, ge=1, le=20)


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
    theme_stock_link_count: int = 0
    unique_stock_count: int = 0
    price_api_call_count: int = 0
    rest_post_calls: int = 0
    auth_token_issue_count: int = 0
    ka10001_calls: int = 0
    ka10015_calls: int = 0
    price_fetch_ms: int = 0
    calc_ms: int = 0
    db_upsert_ms: int = 0
    total_ms: int = 0
    items: list[MarketThemeReturnRefreshItem] = Field(default_factory=list)
    message: str | None = None


class MarketThemeReturnRecalculationPreview(BaseModel):
    theme_id: int
    theme_name: str
    connected_stock_count: int = 0
    period_from: str | None = None
    period_to: str | None = None
    data_source: str = "STORED_STOCK_DAILY_PRICES"


class MarketThemeReturnRecalculationResponse(MarketThemeReturnRecalculationPreview):
    success: bool = True
    processed_date_count: int = 0
    inserted_count: int = 0
    updated_count: int = 0
    skipped_date_count: int = 0
    recalculated_at: str


class MarketThemePriceFlowFailureItem(BaseModel):
    stock_id: int | None = None
    stock_code: str | None = None
    stock_name: str | None = None
    stage: str
    message: str
    error_code: str = "COLLECTION_ERROR"
    user_message: str | None = None
    internal_summary: str | None = None
    retryable: bool = True


class MarketThemeCollectionStageSummary(BaseModel):
    target_count: int = 0
    attempted_count: int = 0
    success_count: int = 0
    up_to_date_count: int = 0
    no_data_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    inserted_rows: int = 0
    updated_rows: int = 0


class MarketThemePriceFlowStockResult(BaseModel):
    stock_id: int
    stock_code: str
    stock_name: str
    market: str | None = None
    provider: str = "kiwoom_rest"
    collect_start_date: str | None = None
    collect_end_date: str | None = None
    price_status: str = "SKIPPED"
    technical_status: str = "SKIPPED"
    investor_status: str = "SKIPPED"
    program_status: str = "SKIPPED"
    price_response_rows: int = 0
    flow_response_rows: int = 0
    price_inserted_rows: int = 0
    price_updated_rows: int = 0
    flow_inserted_rows: int = 0
    flow_updated_rows: int = 0
    latest_price_date: str | None = None
    latest_investor_date: str | None = None
    latest_program_date: str | None = None
    skip_reason: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class MarketThemePriceFlowRefreshResponse(MarketThemeReturnRefreshResponse):
    run_id: int | None = None
    job_status: str = "COMPLETED"
    price_success_count: int = 0
    price_failed_count: int = 0
    price_inserted_count: int = 0
    price_updated_count: int = 0
    technical_success_count: int = 0
    technical_failed_count: int = 0
    technical_saved_count: int = 0
    investor_success_count: int = 0
    investor_failed_count: int = 0
    program_success_count: int = 0
    program_failed_count: int = 0
    flow_inserted_count: int = 0
    flow_updated_count: int = 0
    latest_price_date: str | None = None
    latest_investor_flow_date: str | None = None
    latest_program_flow_date: str | None = None
    collection_mode: str = "FULL"
    processed_stock_codes: list[str] = Field(default_factory=list)
    price_stage: MarketThemeCollectionStageSummary = Field(default_factory=MarketThemeCollectionStageSummary)
    technical_stage: MarketThemeCollectionStageSummary = Field(default_factory=MarketThemeCollectionStageSummary)
    investor_stage: MarketThemeCollectionStageSummary = Field(default_factory=MarketThemeCollectionStageSummary)
    program_stage: MarketThemeCollectionStageSummary = Field(default_factory=MarketThemeCollectionStageSummary)
    theme_return_stage: MarketThemeCollectionStageSummary = Field(default_factory=MarketThemeCollectionStageSummary)
    target_results: list[MarketThemePriceFlowStockResult] = Field(default_factory=list)
    failure_items: list[MarketThemePriceFlowFailureItem] = Field(default_factory=list)


class MarketThemePriceFlowJobStartResponse(BaseModel):
    job_id: str
    status: str = "PENDING"
    message: str
    requested_at: str


class MarketThemePriceFlowJobStatusResponse(BaseModel):
    job_id: str
    status: str
    stage: str
    completed_count: int = 0
    total_count: int = 0
    current_stage: str
    current_stage_label: str
    completed_stock_count: int = 0
    total_stock_count: int = 0
    failed_stock_count: int = 0
    price_result: MarketThemeCollectionStageSummary = Field(default_factory=MarketThemeCollectionStageSummary)
    technical_indicator_result: MarketThemeCollectionStageSummary = Field(default_factory=MarketThemeCollectionStageSummary)
    investor_flow_result: MarketThemeCollectionStageSummary = Field(default_factory=MarketThemeCollectionStageSummary)
    program_flow_result: MarketThemeCollectionStageSummary = Field(default_factory=MarketThemeCollectionStageSummary)
    theme_return_result: MarketThemeCollectionStageSummary = Field(default_factory=MarketThemeCollectionStageSummary)
    requested_at: str
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    failures: list[MarketThemePriceFlowFailureItem] = Field(default_factory=list)
    message: str | None = None
    result: MarketThemePriceFlowRefreshResponse | None = None


class MarketThemeReturnStockItem(BaseModel):
    stock_id: int
    stock_code: str | None = None
    stock_name: str
    stock_memo: str | None = None
    trading_value_100m: float | None = None
    change_rate: float | None = None
    current_price: int | None = None
    data_status: str = "missing"
    error_message: str | None = None
    flow_summary: StockDailyFlowSummary | None = None


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
    flow_summary: ThemeDailyFlowSummary | None = None
    stocks: list[MarketThemeReturnStockItem] = Field(default_factory=list)


class MarketThemeMonthlyReturnDailyItem(BaseModel):
    return_date: str
    avg_change_rate: float | None = None
    rolling_30d_change_rate: float | None = None
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
    rolling_30d_change_rate: float | None = None
    weighted_return_10d: float | None = None
    weighted_return_score: float | None = None
    positive_days_10d: int = 0
    observed_days_10d: int = 0
    persistence_10d: float | None = None
    recent_5d_return: float | None = None
    previous_5d_return: float | None = None
    momentum_delta: float | None = None
    momentum_score: float | None = None
    last_positive_impulse_date: str | None = None
    days_since_positive_impulse: int | None = None
    freshness_score: float | None = None
    rolling_30d_peak: float | None = None
    rolling_30d_peak_gap: float | None = None
    stale_penalty: float = 0
    theme_strength_score: float | None = None
    strength_status_code: str = "INSUFFICIENT"
    strength_status_name: str = "데이터 부족"
    persistence_rank: int | None = None
    current_strength_rank: int | None = None
    rolling_30d_rank: int | None = None
    daily_returns: list[MarketThemeMonthlyReturnDailyItem] = Field(default_factory=list)


class MarketThemeMonthlyReturnSummaryTopItem(BaseModel):
    theme_id: int
    theme_name: str
    monthly_compound_return: float | None = None
    period_compound_return: float | None = None
    total_trading_value_100m: float | None = None
    continuous_rising_days: int | None = None
    rolling_30d_change_rate: float | None = None
    theme_strength_score: float | None = None
    persistence_10d: float | None = None
    strength_status_code: str | None = None
    strength_status_name: str | None = None


class MarketThemeMonthlyReturnSummary(BaseModel):
    top_rising_theme: MarketThemeMonthlyReturnSummaryTopItem | None = None
    top_falling_theme: MarketThemeMonthlyReturnSummaryTopItem | None = None
    top_trading_value_theme: MarketThemeMonthlyReturnSummaryTopItem | None = None
    rising_day_theme: MarketThemeMonthlyReturnSummaryTopItem | None = None
    top_continuous_rising_theme: MarketThemeMonthlyReturnSummaryTopItem | None = None
    current_strength_top: MarketThemeMonthlyReturnSummaryTopItem | None = None
    rolling_30d_top: MarketThemeMonthlyReturnSummaryTopItem | None = None
    trading_value_top: MarketThemeMonthlyReturnSummaryTopItem | None = None
    persistence_top: MarketThemeMonthlyReturnSummaryTopItem | None = None


class MarketThemeMonthlyReturnResponse(BaseModel):
    month: str | None = None
    end_date: str | None = None
    days: int | None = None
    active_only: bool = True
    display_start_date: str
    display_end_date: str
    sort_by: str | None = None
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
    theme_strength_score: float = 0
    return_score: float = 0
    trading_value_score: float = 0
    breadth_score: float = 0
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
    change_rate: float | None = None


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
    theme_strength_score: float = 0
    return_score: float = 0
    trading_value_score: float = 0
    breadth_score: float = 0
    rank_score: float = 0
    rank_basis: str = "auto"
    stocks: list[MonthlyThemeFlowStockItem] = Field(default_factory=list)


class MonthlyThemeFlowCalendarDayItem(BaseModel):
    trade_date: str
    event_count: int = 0
    related_stock_count: int = 0
    themes: list[MonthlyThemeFlowCalendarThemeItem] = Field(default_factory=list)
    memo_items: list[MonthlyThemeFlowMemoItem] = Field(default_factory=list)


class MonthlySupplySummaryStockItem(BaseModel):
    rank: int
    stock_id: int | None = None
    stock_code: str | None = None
    stock_name: str
    appearance_count: int
    latest_detected_date: str | None = None


class MonthlySupplySummaryThemeItem(BaseModel):
    theme_id: int
    theme_name: str
    appearance_count: int
    latest_appearance_date: str | None = None
    unique_stock_count: int = 0


class MonthlySupplySummary30d(BaseModel):
    period_start_date: str
    period_end_date: str
    appeared_theme_count: int = 0
    top_theme: MonthlySupplySummaryThemeItem | None = None
    top_stocks: list[MonthlySupplySummaryStockItem] = Field(default_factory=list)

class SupplyTopStockReturnPoint(BaseModel):
    trade_date: str
    close: float | None = None
    daily_return: float | None = None
    cumulative_return: float | None = None
    is_supply_date: bool = False


class SupplyTopStockPriceReadiness(BaseModel):
    total_stock_count: int = 0
    ready_stock_count: int = 0
    fallback_ready_stock_count: int = 0
    partial_stock_count: int = 0
    missing_stock_count: int = 0
    readiness_rate: float = 0
    missing_stock_ids: list[int] = Field(default_factory=list)
    missing_stock_codes: list[str] = Field(default_factory=list)
    no_price_data_count: int = 0
    no_base_price_count: int = 0
    insufficient_observation_count: int = 0


class SupplyTopStockReturnTrendItem(BaseModel):
    rank: int
    stock_id: int
    stock_code: str
    stock_name: str
    appearance_count: int
    appearance_dates: list[str] = Field(default_factory=list)
    latest_detected_date: str | None = None
    price_data_status: str = "NO_PRICE_DATA"
    price_data_status_name: str = "가격 없음"
    price_data_reason: str = ""
    price_observation_count: int = 0
    expected_trade_date_count: int = 0
    price_coverage_rate: float = 0
    base_price_date: str | None = None
    base_close: float | None = None
    latest_price_date: str | None = None
    latest_close: float | None = None
    latest_daily_return: float | None = None
    latest_cumulative_return: float | None = None
    has_sufficient_price_data: bool = False
    points: list[SupplyTopStockReturnPoint] = Field(default_factory=list)


class SupplyTopStockReturnTrendResponse(BaseModel):
    period_start_date: str
    period_end_date: str
    price_data_end_date: str | None = None
    last_price_collection_date: str | None = None
    ranking_basis: str = "UNIQUE_STOCK_SUPPLY_DAYS"
    limit: int = 20
    trade_dates: list[str] = Field(default_factory=list)
    price_readiness: SupplyTopStockPriceReadiness
    stocks: list[SupplyTopStockReturnTrendItem] = Field(default_factory=list)


class SupplyTopStockPriceCollectRequest(BaseModel):
    period_start_date: str
    period_end_date: str
    limit: int = Field(default=20, ge=1, le=20)


class SupplyTopStockPriceCollectItem(BaseModel):
    stock_id: int
    stock_code: str
    stock_name: str
    status: str
    pages_fetched: int = 0
    collected_count: int = 0
    saved_count: int = 0
    collection_mode: str
    collect_start_date: str
    collect_end_date: str
    price_data_status_before: str
    price_data_status_after: str
    error_message: str | None = None


class SupplyTopStockPriceCollectResponse(BaseModel):
    period_start_date: str
    period_end_date: str
    collect_start_date: str
    collect_end_date: str
    last_price_collection_date: str | None = None
    top_stock_count: int = 0
    target_stock_count: int = 0
    success_count: int = 0
    partial_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    saved_price_count: int = 0
    total_api_calls: int = 0
    total_pages: int = 0
    total_ms: int = 0
    before_readiness: SupplyTopStockPriceReadiness
    after_readiness: SupplyTopStockPriceReadiness
    results: list[SupplyTopStockPriceCollectItem] = Field(default_factory=list)

class MonthlySupplyClassificationDiagnostics(BaseModel):
    classification_basis: str = "CURRENT_ACTIVE_THEME_MAPPING"
    event_count: int = 0
    unique_stock_count: int = 0
    active_theme_count: int = 0
    reclassified_event_stock_count: int = 0
    unclassified_stock_count: int = 0
    period_start_date: str
    period_end_date: str

class MonthlyThemeFlowCalendarResponse(BaseModel):
    success: bool
    month: str
    start_date: str
    end_date: str
    summary_30d: MonthlySupplySummary30d
    diagnostics: MonthlySupplyClassificationDiagnostics
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
    diagnostics: MonthlySupplyClassificationDiagnostics
    themes: list[MonthlyThemeFlowTrendTheme] = Field(default_factory=list)


class MonthlyThemeCellDetailTheme(BaseModel):
    id: int
    name: str
    group_name: str | None = None


class MonthlyThemeCellDetailPeriod(BaseModel):
    from_date: str
    to_date: str


class MonthlyThemeCellDetailSummary(BaseModel):
    appearance_days: int = 0
    unique_stock_count: int = 0
    selected_stock_count: int = 0
    selected_avg_change_rate: float | None = None
    selected_trading_value_100m: float | None = None
    rise_count: int = 0
    fall_count: int = 0
    flat_count: int = 0
    missing_change_count: int = 0
    flow_ready_count: int = 0
    flow_total_count: int = 0
    first_appearance_date: str | None = None
    latest_appearance_date: str | None = None
    recent_appearance_dates: list[str] = Field(default_factory=list)
    monthly_avg_change_rate: float | None = None


class MonthlyThemeCellDetailResponse(BaseModel):
    theme: MonthlyThemeCellDetailTheme
    selected_date: str
    period: MonthlyThemeCellDetailPeriod
    summary: MonthlyThemeCellDetailSummary
    stocks: list[MarketThemeReturnStockItem] = Field(default_factory=list)
    chart_reference: str = "CURRENT"
    queried_at: str

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
