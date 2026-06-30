from __future__ import annotations

from pydantic import BaseModel, Field


class MarketIndicator(BaseModel):
    id: int | None = None
    indicator_code: str
    indicator_name: str
    category: str
    subcategory: str | None = None
    data_frequency: str
    chart_type: str
    unit: str | None = None
    unit_label: str | None = None
    value_label: str | None = None
    base_line_value: float | None = None
    display_order: int = 0
    priority_rank: int = 0
    description: str | None = None
    interpretation_note: str | None = None
    higher_value_meaning: str | None = None
    lower_value_meaning: str | None = None
    is_active: bool = True
    collection_status: str = "WAITING"
    latest_value: float | None = None
    latest_value_date: str | None = None
    latest_change_value: float | None = None
    latest_change_pct: float | None = None
    latest_yoy_pct: float | None = None
    latest_mom_pct: float | None = None


class MarketIndicatorListResponse(BaseModel):
    items: list[MarketIndicator] = Field(default_factory=list)
    category_counts: dict[str, int] = Field(default_factory=dict)


class MarketIndicatorValue(BaseModel):
    id: int | None = None
    indicator_code: str
    value_date: str
    period_label: str | None = None
    value: float | None = None
    open_value: float | None = None
    high_value: float | None = None
    low_value: float | None = None
    close_value: float | None = None
    change_value: float | None = None
    change_pct: float | None = None
    mom_pct: float | None = None
    yoy_pct: float | None = None
    normalized_value: float | None = None
    source_provider: str | None = None
    source_unit: str | None = None
    is_preliminary: bool = False
    release_date: str | None = None


class MarketIndicatorValueResponse(BaseModel):
    indicator_code: str
    indicator_name: str | None = None
    items: list[MarketIndicatorValue] = Field(default_factory=list)


class MarketIndicatorProviderMapping(BaseModel):
    id: int | None = None
    indicator_code: str
    indicator_name: str | None = None
    provider: str
    api_type: str | None = None
    api_id: str | None = None
    endpoint_url: str | None = None
    provider_symbol: str | None = None
    request_params_json: str | None = None
    is_enabled: bool = False
    is_verified: bool = False
    verified_at: str | None = None
    last_test_status: str | None = None
    last_test_message: str | None = None
    last_tested_at: str | None = None


class MarketIndicatorProviderMappingListResponse(BaseModel):
    items: list[MarketIndicatorProviderMapping] = Field(default_factory=list)


class ExternalProviderStatus(BaseModel):
    provider: str
    display_name: str
    configured: bool
    masked_key: str | None = None
    status: str
    message: str
    last_checked_at: str


class ExternalProviderStatusListResponse(BaseModel):
    items: list[ExternalProviderStatus] = Field(default_factory=list)


class MarketIndicatorCollectRequest(BaseModel):
    indicator_codes: list[str] | None = None


class MarketIndicatorCollectResult(BaseModel):
    indicator_code: str
    status: str
    message: str


class MarketIndicatorCollectResponse(BaseModel):
    requested_count: int
    success_count: int = 0
    waiting_count: int = 0
    failed_count: int = 0
    message: str
    results: list[MarketIndicatorCollectResult] = Field(default_factory=list)
