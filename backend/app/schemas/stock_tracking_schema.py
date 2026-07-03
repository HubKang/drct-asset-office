from __future__ import annotations

from pydantic import BaseModel, Field


StockTrackingStatus = str
StockTrackingPriceStatus = str


class StockTrackingGroupBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    success_rule_note: str | None = None
    fail_rule_note: str | None = None
    observation_note: str | None = None
    is_active: int = 1


class StockTrackingGroupCreateRequest(StockTrackingGroupBase):
    pass


class StockTrackingGroupUpdateRequest(StockTrackingGroupBase):
    pass


class StockTrackingGroupResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    success_rule_note: str | None = None
    fail_rule_note: str | None = None
    observation_note: str | None = None
    is_active: int
    item_count: int = 0
    tracking_count: int = 0
    created_at: str
    updated_at: str


class RegisterTrackingItemsFromCandidatesRequest(BaseModel):
    group_id: int
    candidate_ids: list[int] = Field(default_factory=list)


class StockTrackingRegisterItemResult(BaseModel):
    candidate_id: int
    stock_code: str | None = None
    stock_name: str | None = None
    status: str
    message: str | None = None


class RegisterTrackingItemsFromCandidatesResponse(BaseModel):
    requested_count: int = 0
    success: bool
    created_count: int
    skipped_count: int
    item_ids: list[int] = Field(default_factory=list)
    items: list[StockTrackingRegisterItemResult] = Field(default_factory=list)
    message: str


class CreateTrackingFromConditionResultItem(BaseModel):
    stock_code: str
    stock_name: str | None = None
    market: str | None = None
    current_price: float | None = None
    change_rate: float | None = None
    volume: int | None = None
    trading_value: float | None = None


class CreateTrackingFromConditionResultsRequest(BaseModel):
    group_id: int
    condition_no: str | None = None
    condition_name: str | None = None
    detected_date: str
    items: list[CreateTrackingFromConditionResultItem] = Field(default_factory=list)


class CreateTrackingFromConditionResultStatus(BaseModel):
    stock_code: str | None = None
    stock_name: str | None = None
    status: str
    tracking_item_id: int | None = None
    reason: str | None = None


class CreateTrackingFromConditionResultsResponse(BaseModel):
    requested_count: int = 0
    success: bool
    created_count: int
    skipped_count: int
    item_ids: list[int] = Field(default_factory=list)
    items: list[CreateTrackingFromConditionResultStatus] = Field(default_factory=list)
    message: str


class UpdateStockTrackingReviewRequest(BaseModel):
    status: str
    review_note: str | None = None


class StockTrackingItemResponse(BaseModel):
    id: int
    group_id: int
    group_name: str
    candidate_id: int | None = None
    condition_no: str | None = None
    condition_name: str | None = None
    stock_id: int | None = None
    stock_code: str | None = None
    stock_name: str | None = None
    detected_date: str | None = None
    tracking_base_date: str
    base_price: float | None = None
    base_change_rate: float | None = None
    base_volume: int | None = None
    base_trading_value: int | None = None
    entry_close_price: float | None = None
    entry_close_date: str | None = None
    latest_close_price: float | None = None
    latest_close_date: str | None = None
    tracking_return_pct: float | None = None
    price_updated_at: str | None = None
    status: str
    review_date: str | None = None
    review_note: str | None = None
    price_status: str
    created_at: str
    updated_at: str


class StockTrackingItemListResponse(BaseModel):
    items: list[StockTrackingItemResponse]
    total: int


class CollectStockTrackingPricesRequest(BaseModel):
    item_ids: list[int] = Field(default_factory=list)
    source: str = "kiwoom_rest"
    overlap_days: int = 7
    force_full_refresh: bool = False


class CollectStockTrackingPriceItemResult(BaseModel):
    item_id: int
    stock_code: str | None = None
    stock_name: str | None = None
    status: str
    collected_count: int = 0
    saved_count: int = 0
    last_collected_date: str | None = None
    target_start_date: str | None = None
    latest_trade_date_before: str | None = None
    requested_start_date: str | None = None
    requested_end_date: str | None = None
    collection_mode: str | None = None
    overlap_days: int = 7
    force_full_refresh: bool = False
    message: str | None = None


class CollectStockTrackingPricesResponse(BaseModel):
    requested_count: int
    success_count: int
    partial_count: int = 0
    failed_count: int = 0
    items: list[CollectStockTrackingPriceItemResult] = Field(default_factory=list)
    message: str


class StockTrackingChartPrice(BaseModel):
    date: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None
    trading_value: int | None = None
    ma5: float | None = None
    ma10: float | None = None
    ma20: float | None = None
    ma60: float | None = None
    ma120: float | None = None


class StockTrackingChartResponse(BaseModel):
    item_id: int
    stock_code: str | None = None
    stock_name: str | None = None
    tracking_base_date: str
    review_date: str | None = None
    prices: list[StockTrackingChartPrice] = Field(default_factory=list)


class StockTrackingImageResponse(BaseModel):
    id: int
    tracking_item_id: int
    image_url: str
    image_path: str | None = None
    original_filename: str | None = None
    image_type: str
    image_type_label: str | None = None
    caption: str | None = None
    created_at: str
    updated_at: str | None = None


class StockTrackingImageListResponse(BaseModel):
    items: list[StockTrackingImageResponse] = Field(default_factory=list)


class StockTrackingBaseMetricSummary(BaseModel):
    close_vs_ma20_pct: float | None = None
    close_vs_ma60_pct: float | None = None
    recent_5d_return_pct: float | None = None
    trading_value_ratio_20: float | None = None
    ma60_slope_5d_pct: float | None = None
    high_vs_close_pct: float | None = None
    close_position_pct: float | None = None


class StockTrackingGroupBaseMetricComparison(BaseModel):
    avg: StockTrackingBaseMetricSummary = Field(default_factory=StockTrackingBaseMetricSummary)
    success_avg: StockTrackingBaseMetricSummary = Field(default_factory=StockTrackingBaseMetricSummary)
    fail_avg: StockTrackingBaseMetricSummary = Field(default_factory=StockTrackingBaseMetricSummary)
    diff: StockTrackingBaseMetricSummary = Field(default_factory=StockTrackingBaseMetricSummary)


class StockTrackingGroupAnalysisSample(BaseModel):
    item_id: int
    stock_code: str | None = None
    stock_name: str | None = None
    tracking_base_date: str
    review_date: str | None = None
    review_note: str | None = None
    current_return_pct: float | None = None
    max_return_pct: float | None = None
    max_drawdown_pct: float | None = None
    elapsed_trading_days: int | None = None
    close_vs_ma20_pct: float | None = None
    close_vs_ma60_pct: float | None = None
    recent_5d_return_pct: float | None = None
    trading_value_ratio_20: float | None = None
    ma60_slope_5d_pct: float | None = None
    high_vs_close_pct: float | None = None
    close_position_pct: float | None = None


class StockTrackingGroupAnalysisResponse(BaseModel):
    group_id: int
    group_name: str
    total_count: int = 0
    tracking_count: int = 0
    hold_count: int = 0
    success_count: int = 0
    fail_count: int = 0
    excluded_count: int = 0
    completed_count: int = 0
    success_rate: float | None = None
    return_calculated_count: int = 0
    base_metric_calculated_count: int = 0
    base_metric_summary: StockTrackingGroupBaseMetricComparison = Field(default_factory=StockTrackingGroupBaseMetricComparison)
    avg_current_return_pct: float | None = None
    avg_max_return_pct: float | None = None
    avg_max_drawdown_pct: float | None = None
    avg_elapsed_trading_days: float | None = None
    success_avg_current_return_pct: float | None = None
    success_avg_max_return_pct: float | None = None
    success_avg_max_drawdown_pct: float | None = None
    success_avg_elapsed_trading_days: float | None = None
    fail_avg_current_return_pct: float | None = None
    fail_avg_max_return_pct: float | None = None
    fail_avg_max_drawdown_pct: float | None = None
    fail_avg_elapsed_trading_days: float | None = None
    diff_avg_current_return_pct: float | None = None
    diff_avg_max_return_pct: float | None = None
    diff_avg_max_drawdown_pct: float | None = None
    success_samples: list[StockTrackingGroupAnalysisSample] = Field(default_factory=list)
    fail_samples: list[StockTrackingGroupAnalysisSample] = Field(default_factory=list)


class StockTrackingGroupAnalysisListResponse(BaseModel):
    items: list[StockTrackingGroupAnalysisResponse] = Field(default_factory=list)
