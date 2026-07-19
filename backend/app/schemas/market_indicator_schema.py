from __future__ import annotations

from typing import Any

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


class MarketIndicatorReadiness(BaseModel):
    indicator_code: str
    indicator_name: str | None = None
    provider: str | None = None
    provider_symbol: str | None = None
    data_frequency: str | None = None
    unit_label: str | None = None
    collection_status: str | None = None
    readiness: str
    readiness_reason: str | None = None
    data_count: int = 0
    first_value_date: str | None = None
    latest_value_date: str | None = None
    latest_value: float | None = None
    latest_collected_at: str | None = None
    recommended_minimum_count: int = 0
    insufficient_count: int = 0
    mapping_ready: bool = False
    data_ready: bool = False
    chart_ready: bool = False
    compare_ready: bool = False
    signal_ready: bool = False
    supported_transforms: list[str] = Field(default_factory=list)


class MarketIndicatorReadinessListResponse(BaseModel):
    items: list[MarketIndicatorReadiness] = Field(default_factory=list)
    summary_counts: dict[str, int] = Field(default_factory=dict)


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




class MarketIndicatorProviderMappingUpsertRequest(BaseModel):
    provider: str = "BOK_ECOS"
    api_type: str | None = "ECONOMIC_STAT"
    api_id: str | None = None
    endpoint_url: str | None = None
    provider_symbol: str | None = None
    request_params_json: dict[str, Any] | str | None = None
    is_enabled: bool = False


class MarketIndicatorProviderMappingTestRequest(BaseModel):
    start_date: str | None = None
    end_date: str | None = None
    save_result: bool = True


class MarketIndicatorProviderMappingTestResponse(BaseModel):
    indicator_code: str
    provider: str
    status: str
    message: str
    sample_count: int = 0
    sample_rows: list[dict[str, Any]] = Field(default_factory=list)


class EcosItemListResponse(BaseModel):
    stat_code: str
    status: str
    message: str
    list_total_count: int = 0
    items: list[dict[str, Any]] = Field(default_factory=list)


class EcosTableItem(BaseModel):
    p_stat_code: str | None = None
    stat_code: str | None = None
    stat_name: str | None = None
    cycle: str | None = None
    srch_yn: str | None = None
    org_name: str | None = None


class EcosTableListResponse(BaseModel):
    status: str
    message: str
    total_count: int = 0
    items: list[EcosTableItem] = Field(default_factory=list)


class EcosTableSearchResponse(BaseModel):
    keyword: str
    status: str
    message: str
    searched_count: int = 0
    items: list[EcosTableItem] = Field(default_factory=list)


class EcosDiscoverCandidatesRequest(BaseModel):
    indicator_codes: list[str] | None = None
    max_depth: int = 2
    cycle: str | None = None


class EcosCandidate(BaseModel):
    p_stat_code: str | None = None
    stat_code: str | None = None
    stat_name: str | None = None
    cycle: str | None = None
    srch_yn: str | None = None
    org_name: str | None = None
    score: int = 0
    reason: str | None = None


class EcosIndicatorCandidates(BaseModel):
    indicator_code: str
    indicator_name: str | None = None
    keywords: list[str] = Field(default_factory=list)
    candidates: list[EcosCandidate] = Field(default_factory=list)


class EcosDiscoverCandidatesResponse(BaseModel):
    status: str
    message: str
    searched_count: int = 0
    items: list[EcosIndicatorCandidates] = Field(default_factory=list)


class EcosMappingCandidate(BaseModel):
    indicator_code: str
    indicator_name: str | None = None
    stat_code: str
    stat_name: str | None = None
    cycle: str | None = None
    item_code1: str
    item_name1: str | None = None
    provider_symbol: str
    score: int = 0
    reason: str | None = None
    source_unit: str | None = None
    request_params_json: dict[str, Any] = Field(default_factory=dict)


class EcosIndicatorMappingCandidates(BaseModel):
    indicator_code: str
    indicator_name: str | None = None
    candidates: list[EcosMappingCandidate] = Field(default_factory=list)


class EcosDiscoverMappingCandidatesRequest(BaseModel):
    indicator_codes: list[str] | None = None
    top_table_count: int = 5
    max_item_count: int = 200


class EcosDiscoverMappingCandidatesResponse(BaseModel):
    status: str
    message: str
    items: list[EcosIndicatorMappingCandidates] = Field(default_factory=list)


class EcosMappingCandidateTestRequest(BaseModel):
    provider: str = "BOK_ECOS"
    stat_code: str
    cycle: str = "D"
    item_code1: str
    item_name1: str | None = None
    scale: float = 1
    source_unit: str | None = None



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
    start_date: str | None = None
    end_date: str | None = None


class MarketIndicatorCollectResult(BaseModel):
    indicator_code: str
    status: str
    message: str
    saved_count: int = 0
    received_count: int = 0
    inserted_count: int = 0
    updated_count: int = 0
    unchanged_count: int = 0
    requested_from: str | None = None
    requested_to: str | None = None
    latest_value: float | None = None
    latest_value_date: str | None = None


class MarketIndicatorCollectResponse(BaseModel):
    requested_count: int
    success_count: int = 0
    waiting_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    message: str
    results: list[MarketIndicatorCollectResult] = Field(default_factory=list)
