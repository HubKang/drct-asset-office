from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MarketThemeCreateRequest(BaseModel):
    theme_name: str = Field(min_length=1)
    theme_code: str | None = None
    theme_type: str = Field(min_length=1)
    description: str | None = None
    keywords: list[str] = Field(default_factory=list)
    parent_theme_id: int | None = None
    is_supply_theme: int = 0
    sort_order: int = 0
    is_active: int = 1


class MarketThemeUpdateRequest(BaseModel):
    theme_name: str = Field(min_length=1)
    theme_type: str = Field(min_length=1)
    description: str | None = None
    keywords: list[str] = Field(default_factory=list)
    parent_theme_id: int | None = None
    is_supply_theme: int = 0
    sort_order: int = 0
    is_active: int = 1


class MarketThemeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    theme_name: str
    theme_code: str
    theme_type: str
    description: str | None
    keywords: list[str]
    parent_theme_id: int | None
    is_supply_theme: int
    is_active: int
    sort_order: int
    stock_count: int
    created_at: str
    updated_at: str
