from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

THEME_LEVEL_GROUP = "THEME_GROUP"
THEME_LEVEL_THEME = "THEME"


class MarketThemeCreateRequest(BaseModel):
    theme_name: str = Field(min_length=1)
    theme_code: str | None = None
    theme_type: str = Field(min_length=1)
    theme_level: str = THEME_LEVEL_THEME
    description: str | None = None
    keywords: list[str] = Field(default_factory=list)
    parent_theme_id: int | None = None
    is_supply_theme: int = 0
    sort_order: int = 0
    is_active: int = 1


class MarketThemeUpdateRequest(BaseModel):
    theme_name: str = Field(min_length=1)
    theme_type: str = Field(min_length=1)
    theme_level: str = THEME_LEVEL_THEME
    description: str | None = None
    keywords: list[str] = Field(default_factory=list)
    parent_theme_id: int | None = None
    is_supply_theme: int = 0
    sort_order: int = 0
    is_active: int = 1


class MarketThemeLatestReturnSummary(BaseModel):
    return_date: str | None = None
    avg_change_rate: float | None = None
    last_refreshed_at: str | None = None
    stock_count: int = 0
    success_stock_count: int = 0
    failed_stock_count: int = 0
    total_trading_value_100m: float | None = None


class MarketThemeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    theme_name: str
    theme_code: str
    theme_type: str
    theme_level: str
    description: str | None
    keywords: list[str]
    parent_theme_id: int | None
    parent_theme_name: str | None = None
    is_supply_theme: int
    is_active: int
    sort_order: int
    stock_count: int
    linked_stock_count: int = 0
    keyword_count: int = 0
    child_theme_count: int = 0
    supply_child_theme_count: int = 0
    latest_return: MarketThemeLatestReturnSummary | None = None
    created_at: str
    updated_at: str


class MarketThemeDeleteResponse(BaseModel):
    deleted_theme_id: int
    deleted_theme_name: str
    deleted_theme_count: int
    deleted_related_row_count: int
    detached_event_reference_count: int
