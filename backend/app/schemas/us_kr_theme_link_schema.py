from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class UsKrThemeLinkInput(BaseModel):
    us_theme_id: int = Field(gt=0)
    kr_theme_id: int = Field(gt=0)
    memo: str | None = Field(default=None, max_length=500)


class UsKrThemeLinkUpdate(BaseModel):
    us_theme_id: int | None = Field(default=None, gt=0)
    kr_theme_id: int | None = Field(default=None, gt=0)
    memo: str | None = Field(default=None, max_length=500)


class ThemeLinkOption(BaseModel):
    id: int
    group_name: str
    theme_name: str
    active: int
    linked: bool


class UsKrThemeLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    us_theme_id: int
    us_group_name: str
    us_theme_name: str
    kr_theme_id: int
    kr_group_name: str
    kr_theme_name: str
    memo: str | None
    active: int
    created_at: str
    updated_at: str


class UsKrThemeLinkSummary(BaseModel):
    us_active_themes: int
    kr_active_themes: int
    linked_themes: int
    unlinked_us_themes: int
    unlinked_kr_themes: int


class UsKrThemeLinkOverview(BaseModel):
    summary: UsKrThemeLinkSummary
    links: list[UsKrThemeLinkResponse]
    us_themes: list[ThemeLinkOption]
    kr_themes: list[ThemeLinkOption]


class UsKrLeadPair(BaseModel):
    us_trade_date: str
    us_value: float
    kr_trade_date: str
    kr_return: float
    calendar_gap_days: int
    direction_match: bool | None


class UsKrLeadThreshold(BaseModel):
    direction: str
    condition: str
    threshold: float
    sample_count: int
    response_rate: float | None
    avg_kr_return: float | None
    median_kr_return: float | None


class UsKrLeadMetrics(BaseModel):
    candidate_count: int
    sample_count: int
    excluded_count: int
    direction_sample_count: int
    direction_match_rate: float | None
    us_up_kr_up_rate: float | None
    us_down_kr_down_rate: float | None
    avg_kr_return: float | None
    median_kr_return: float | None
    pearson_correlation: float | None
    spearman_correlation: float | None
    regression_slope: float | None
    regression_intercept: float | None
    sample_guidance: str


class UsKrLeadAnalysisResponse(BaseModel):
    link: UsKrThemeLinkResponse
    window: int | None
    us_metric: str
    us_metric_label: str
    kr_metric_label: str
    latest_us_date: str | None
    latest_kr_date: str | None
    max_calendar_gap_days: int
    metrics: UsKrLeadMetrics
    thresholds: list[UsKrLeadThreshold]
    pairs: list[UsKrLeadPair]


class UsKrTodayObservationItem(BaseModel):
    rank: int
    link_id: int
    us_theme_id: int
    us_group_name: str
    us_theme_name: str
    kr_theme_id: int
    kr_group_name: str
    kr_theme_name: str
    available: bool
    latest_us_date: str | None
    previous_us_date: str | None
    kr_target_date: str | None
    latest_value: float | None
    previous_value: float | None
    delta: float | None
    breadth_ratio: float | None
    valid_stock_count: int
    up_count: int
    down_count: int
    threshold_direction: str | None
    threshold_condition: str | None
    threshold: float | None
    sample_count: int
    response_rate: float | None
    avg_kr_return: float | None
    sample_guidance: str
    missing_reason: str | None


class UsKrTodayObservationSummary(BaseModel):
    linked_count: int
    available_count: int
    missing_count: int
    up_count: int
    down_count: int


class UsKrTodayObservationResponse(BaseModel):
    window: int | None
    us_metric: str
    us_metric_label: str
    latest_us_date: str | None
    previous_us_date: str | None
    kr_target_date: str | None
    max_calendar_gap_days: int
    summary: UsKrTodayObservationSummary
    items: list[UsKrTodayObservationItem]
