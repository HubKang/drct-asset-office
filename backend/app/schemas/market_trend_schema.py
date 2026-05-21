from __future__ import annotations

from pydantic import BaseModel, Field


class TrendDetectionSettingResponse(BaseModel):
    id: int
    setting_key: str
    setting_name: str
    min_market_cap: int
    min_market_cap_krw_100m: float
    min_trading_value: int
    min_trading_value_krw_100m: float
    min_change_rate: float
    min_intraday_range_rate: float | None
    use_market_cap: bool
    use_trading_value: bool
    use_change_rate: bool
    use_intraday_range: bool
    market_scope: str
    is_active: bool


class TrendDetectionSettingUpdateRequest(BaseModel):
    use_market_cap: bool = True
    min_market_cap_krw_100m: float = Field(ge=0)
    use_trading_value: bool = True
    min_trading_value_krw_100m: float = Field(ge=0)
    use_change_rate: bool = True
    min_change_rate: float = Field(ge=0)
    min_intraday_range_rate: float | None = Field(default=None, ge=0)
    use_intraday_range: bool = False
    market_scope: str
    is_active: bool = True


class CollectMarketTrendEventsRequest(BaseModel):
    trade_date: str | None = None


class CollectMarketTrendEventsResponse(BaseModel):
    trade_date: str
    applied_condition: dict[str, object]
    collected_count: int
    inserted_count: int
    duplicated_count: int
    message: str


class CollectMarketPriceSnapshotsRequest(BaseModel):
    snapshot_date: str | None = None
    market_scope: str = "ALL"
    collect_mode: str = "stock_loop"
    limit: int | None = Field(default=None, ge=1)


class CollectMarketPriceSnapshotsResponse(BaseModel):
    snapshot_date: str
    snapshot_time: str
    source: str
    market_scope: str
    collect_mode: str
    requested_count: int
    collected_count: int
    inserted_count: int
    failed_count: int
    skipped_count: int
    matched_stock_count: int
    unmatched_stock_count: int
    failed_markets: list[str] = Field(default_factory=list)
    failed_items: list[str] = Field(default_factory=list)
    message: str


class MarketPriceSnapshotResponse(BaseModel):
    snapshot_date: str
    snapshot_time: str
    stock_id: int | None
    stock_code: str
    stock_name: str | None
    market_type: str | None
    close_price: int | None
    change_rate: float | None
    trading_value: int | None
    market_cap: int | None
    intraday_range_rate: float | None


class DetectEventsFromSnapshotRequest(BaseModel):
    snapshot_date: str | None = None


class DetectEventsFromSnapshotResponse(BaseModel):
    snapshot_date: str
    source_snapshot_count: int
    filtered_count: int
    inserted_count: int
    updated_count: int
    duplicated_count: int
    applied_condition: dict[str, object]
    message: str


class MarketTrendEventResponse(BaseModel):
    event_id: int
    trade_date: str
    stock_id: int
    stock_code: str | None
    stock_name: str | None
    market_type: str | None
    market_cap: int | None
    trading_value: int | None
    change_rate: float | None
    intraday_range_rate: float | None
    event_type: str
    detection_source: str | None
    theme_id: int | None
    theme_name: str | None
    theme_status: str
    reason_summary: str | None
    user_memo: str | None
    applied_condition: dict[str, object]


class AssignThemeToTrendEventRequest(BaseModel):
    theme_id: int
    reason_summary: str | None = None
    user_memo: str | None = None
    also_add_to_theme_stocks: bool = False
    is_primary_for_theme: bool = False


class AssignThemeToTrendEventResponse(BaseModel):
    event_id: int
    theme_id: int
    theme_name: str
    theme_status: str
    added_to_theme_stocks: bool
    already_mapped: bool
    message: str


class DailyThemeFlowItem(BaseModel):
    theme_id: int
    theme_name: str
    is_supply_theme: bool
    detected_stock_count: int
    total_trading_value: int
    total_trading_value_krw_100m: float
    avg_change_rate: float | None
    max_change_rate: float | None
    top_change_stock_name: str | None
    top_trading_value_stock_name: str | None
    trend_rank: int


class DailyThemeFlowResponse(BaseModel):
    trade_date: str
    description: str
    summary: dict[str, int]
    items: list[DailyThemeFlowItem]
