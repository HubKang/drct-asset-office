from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

UsThemeStockRole = Literal["LEADER", "CORE", "RELATED", "ETF"]


def _clean_required(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("이름을 입력해 주세요.")
    return cleaned


class UsThemeGroupInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    sort_order: int = Field(default=100, ge=0, le=9999)
    active: int = Field(default=1, ge=0, le=1)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return _clean_required(value)


class UsThemeGroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    sort_order: int | None = Field(default=None, ge=0, le=9999)
    active: int | None = Field(default=None, ge=0, le=1)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        return _clean_required(value) if value is not None else None


class UsThemeGroupResponse(BaseModel):
    id: int
    name: str
    description: str | None
    sort_order: int
    active: int
    theme_count: int
    active_theme_count: int
    linked_stock_count: int
    created_at: str
    updated_at: str


class UsThemeInput(BaseModel):
    theme_group_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    keywords: list[str] = Field(default_factory=list, max_length=50)
    sort_order: int = Field(default=100, ge=0, le=9999)
    active: int = Field(default=1, ge=0, le=1)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return _clean_required(value)


class UsThemeUpdate(BaseModel):
    theme_group_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    keywords: list[str] | None = Field(default=None, max_length=50)
    sort_order: int | None = Field(default=None, ge=0, le=9999)
    active: int | None = Field(default=None, ge=0, le=1)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        return _clean_required(value) if value is not None else None


class UsThemeResponse(BaseModel):
    id: int
    theme_group_id: int
    theme_group_name: str
    name: str
    description: str | None
    keywords: list[str]
    sort_order: int
    active: int
    linked_stock_count: int
    representative_symbols: list[str]
    latest_return_date: str | None = None
    latest_simple_return: float | None = None
    latest_theme_strength: float | None = None
    latest_breadth_ratio: float | None = None
    created_at: str
    updated_at: str


class UsThemeStockInput(BaseModel):
    us_stock_id: int = Field(gt=0)
    role: UsThemeStockRole = "RELATED"
    is_representative: int = Field(default=0, ge=0, le=1)
    sort_order: int = Field(default=100, ge=0, le=9999)


class UsThemeStockUpdate(BaseModel):
    role: UsThemeStockRole | None = None
    is_representative: int | None = Field(default=None, ge=0, le=1)
    sort_order: int | None = Field(default=None, ge=0, le=9999)
    active: int | None = Field(default=None, ge=0, le=1)


class UsThemeStockResponse(BaseModel):
    mapping_id: int
    theme_id: int
    us_stock_id: int
    symbol: str
    name: str | None
    name_ko: str | None
    exchange: str
    stock_type: str
    naver_code: str | None
    role: UsThemeStockRole
    is_representative: int
    sort_order: int
    active: int
    created_at: str
    updated_at: str


class UsThemeSummaryResponse(BaseModel):
    theme_groups: int
    themes: int
    active_themes: int
    linked_stocks: int


class UsThemeDashboardRankItem(BaseModel):
    theme_id: int
    theme_group_name: str
    theme_name: str
    simple_return: float
    theme_strength: float
    rolling_30d_return: float
    persistence_rate: float
    positive_days: int
    observed_days: int


class UsThemeDashboardSummaryResponse(BaseModel):
    latest_date: str | None
    latest_refreshed_at: str | None
    active_theme_count: int
    top_strength: list[UsThemeDashboardRankItem]
    top_persistence: list[UsThemeDashboardRankItem]


class UsStockChartResponse(BaseModel):
    stock_id: int
    naver_code: str | None
    day: str | None
    week: str | None
    month: str | None
    available: bool


class UsThemeReturnItem(BaseModel):
    theme_id: int
    theme_group_name: str
    theme_name: str
    trade_date: str | None
    simple_return: float | None
    theme_strength: float | None
    trimmed_mean_return: float | None
    median_return: float | None
    breadth_ratio: float | None
    valid_stock_count: int
    up_count: int
    down_count: int
    flat_count: int


class UsThemeReturnListResponse(BaseModel):
    latest_date: str | None
    items: list[UsThemeReturnItem]


class UsThemeTreemapItem(UsThemeReturnItem):
    linked_stock_count: int = 0


class UsThemeTreemapResponse(BaseModel):
    latest_date: str | None
    active_theme_count: int = 0
    linked_stock_count: int = 0
    aggregated_stock_count: int = 0
    items: list[UsThemeTreemapItem]


class UsThemeReturnRecalculateRequest(BaseModel):
    start_date: str | None = None
    end_date: str | None = None
    theme_ids: list[int] | None = Field(default=None, max_length=200)


class UsThemeReturnRecalculateResponse(BaseModel):
    processed_theme_count: int
    processed_date_count: int
    upserted_count: int
    skipped_count: int
    date_from: str | None
    date_to: str | None
    message: str


class UsThemeTrendPoint(BaseModel):
    trade_date: str
    simple_return: float
    theme_strength: float
    rolling_30d_simple_return: float
    rolling_30d_theme_strength: float
    rolling_30d_valid_count: int
    breadth_ratio: float
    valid_stock_count: int
    up_count: int


class UsThemeTrendItem(BaseModel):
    theme_id: int
    theme_group_id: int
    theme_group_name: str
    theme_name: str
    active: int
    points: list[UsThemeTrendPoint]


class UsThemeTrendResponse(BaseModel):
    period: Literal[20, 30, 60]
    dates: list[str]
    items: list[UsThemeTrendItem]


class UsThemeReturnStockItem(BaseModel):
    us_stock_id: int
    symbol: str
    name: str | None
    name_ko: str | None
    exchange: str
    stock_type: str
    naver_code: str | None
    role: UsThemeStockRole
    is_representative: int
    sort_order: int
    active: int
    return_rate: float | None
    daily_return: float | None
    close_price: float | None
    previous_close: float | None


class UsThemeReturnDetailResponse(BaseModel):
    theme_id: int
    theme_name: str
    theme_group_name: str
    description: str | None
    active: int
    trade_date: str | None
    simple_return: float | None
    theme_strength: float | None
    breadth_ratio: float | None
    valid_stock_count: int
    eligible_stock_count: int
    linked_stock_count: int
    up_count: int
    down_count: int
    flat_count: int
    aggregate: UsThemeReturnItem | None
    stocks: list[UsThemeReturnStockItem]


class UsMarketRefreshRequest(BaseModel):
    mode: Literal["INCREMENTAL", "MISSING", "SELECTED", "ALL_ACTIVE", "BACKFILL"] = "INCREMENTAL"
    stock_ids: list[int] | None = Field(default=None, max_length=200)
    trading_days: int = Field(default=260, ge=2, le=1000)


class UsMarketRefreshResponse(BaseModel):
    price: dict
    returns: UsThemeReturnRecalculateResponse
    message: str
