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
    use_intraday_range: bool
    market_scope: str
    is_active: bool


class TrendDetectionSettingUpdateRequest(BaseModel):
    min_market_cap_krw_100m: float = Field(ge=0)
    min_trading_value_krw_100m: float = Field(ge=0)
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

