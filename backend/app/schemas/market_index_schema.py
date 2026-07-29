from __future__ import annotations

from pydantic import BaseModel, Field


class MarketIndexItem(BaseModel):
    id: int
    index_code: str
    index_name: str
    category: str
    market: str
    currency: str
    provider: str
    provider_symbol: str | None = None
    description: str | None = None
    is_active: bool
    display_order: int
    last_collected_date: str | None = None
    collection_status: str
    error_message: str | None = None
    latest_price_date: str | None = None
    latest_close_price: float | None = None
    latest_close: float | None = None
    latest_volume: int | None = None
    latest_trading_value: int | None = None
    recent_5d_return: float | None = None
    recent_20d_return: float | None = None
    recent_5d_return_pct: float | None = None
    recent_20d_return_pct: float | None = None


class MarketIndexListResponse(BaseModel):
    items: list[MarketIndexItem] = Field(default_factory=list)


class MarketIndexDailyPriceItem(BaseModel):
    id: int | None = None
    index_code: str
    price_date: str
    open_price: float | None = None
    high_price: float | None = None
    low_price: float | None = None
    close_price: float | None = None
    volume: int | None = None
    trading_value: int | None = None
    change_rate: float | None = None
    ma5: float | None = None
    ma20: float | None = None
    ma60: float | None = None
    ma120: float | None = None
    source_provider: str | None = None


class MarketIndexDailyPriceListResponse(BaseModel):
    index_code: str
    index_name: str | None = None
    items: list[MarketIndexDailyPriceItem] = Field(default_factory=list)


class MarketIndexCollectRequest(BaseModel):
    index_codes: list[str] | None = None
    start_date: str | None = None
    end_date: str | None = None
    period_years: int = 2
    overlap_days: int = 7
    force_full_refresh: bool = False


class MarketIndexCollectItemResult(BaseModel):
    index_code: str
    index_name: str | None = None
    status: str
    collected_count: int = 0
    saved_count: int = 0
    inserted_count: int = 0
    updated_count: int = 0
    unchanged_count: int = 0
    from_date: str | None = None
    to_date: str | None = None
    collection_mode: str | None = None
    latest_price_date_before: str | None = None
    overlap_days: int = 7
    force_full_refresh: bool = False
    message: str | None = None
    last_collected_date: str | None = None
    error_message: str | None = None


class MarketIndexCollectResponse(BaseModel):
    requested_count: int
    success_count: int
    failed_count: int
    waiting_count: int = 0
    excluded_count: int = 0
    custom_index_required_count: int = 0
    saved_count: int
    message: str
    results: list[MarketIndexCollectItemResult] = Field(default_factory=list)


class MarketIndexCompareSeries(BaseModel):
    index_code: str
    index_name: str | None = None
    points: list[dict] = Field(default_factory=list)


class MarketIndexCompareResponse(BaseModel):
    normalize: bool = True
    start_date: str | None = None
    end_date: str | None = None
    series: list[MarketIndexCompareSeries] = Field(default_factory=list)



class MarketIndexProviderMappingItem(BaseModel):
    id: int | None = None
    index_code: str
    index_name: str | None = None
    provider: str = "KIWOOM_REST"
    api_type: str | None = None
    provider_symbol: str | None = None
    market_type: str | None = None
    indicator_type: str | None = None
    request_params_json: str | None = None
    api_id: str | None = None
    endpoint_url: str | None = None
    is_enabled: bool = False
    is_verified: bool = False
    verified_at: str | None = None
    last_test_status: str | None = None
    last_test_message: str | None = None
    last_tested_at: str | None = None


class MarketIndexProviderMappingListResponse(BaseModel):
    items: list[MarketIndexProviderMappingItem] = Field(default_factory=list)


class MarketIndexProviderMappingUpsertRequest(BaseModel):
    provider: str = "KIWOOM_REST"
    api_type: str | None = None
    provider_symbol: str | None = None
    market_type: str | None = None
    indicator_type: str | None = None
    request_params_json: str | None = None
    api_id: str | None = None
    endpoint_url: str | None = None
    is_enabled: bool = False


class MarketIndexProviderMappingTestRequest(BaseModel):
    provider: str = "KIWOOM_REST"
    api_type: str | None = None
    provider_symbol: str | None = None
    market_type: str | None = None
    request_params_json: str | None = None
    api_id: str | None = None
    endpoint_url: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    save_result: bool = False


class MarketIndexProviderMappingTestResponse(BaseModel):
    index_code: str
    status: str
    sample_count: int = 0
    first_date: str | None = None
    last_date: str | None = None
    message: str
    sample: list[dict] = Field(default_factory=list)

class MarketIndexProviderCodeCollectRequest(BaseModel):
    provider: str = "KIWOOM_REST"
    market_types: list[str] = Field(default_factory=lambda: ["0", "1", "2"])


class MarketIndexProviderCodeCollectResult(BaseModel):
    market_type: str
    count: int = 0
    status: str
    error_message: str | None = None


class MarketIndexProviderCodeCollectResponse(BaseModel):
    requested_count: int
    success_count: int
    failed_count: int
    results: list[MarketIndexProviderCodeCollectResult] = Field(default_factory=list)


class MarketIndexProviderCodeItem(BaseModel):
    id: int | None = None
    provider: str = "KIWOOM_REST"
    market_type: str
    market_code: str | None = None
    code: str
    name: str
    group_name: str | None = None
    source_api_id: str | None = None
    is_active: bool = True
    matched_index_code: str | None = None
    matched_index_name: str | None = None


class MarketIndexProviderCodeListResponse(BaseModel):
    items: list[MarketIndexProviderCodeItem] = Field(default_factory=list)


class MarketIndexSectorCodeAutoMatchResult(BaseModel):
    index_code: str
    index_name: str | None = None
    matched_code: str | None = None
    matched_name: str | None = None
    status: str
    message: str | None = None


class MarketIndexSectorCodeAutoMatchResponse(BaseModel):
    matched_count: int = 0
    waiting_count: int = 0
    results: list[MarketIndexSectorCodeAutoMatchResult] = Field(default_factory=list)

