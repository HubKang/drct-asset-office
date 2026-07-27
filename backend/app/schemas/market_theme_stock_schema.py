from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MarketThemeStockCreateRequest(BaseModel):
    stock_id: int
    is_primary: bool = False


class MarketThemeStockUpdateRequest(BaseModel):
    is_primary: bool | None = None
    is_active: int | None = None
    confidence_score: float | None = None


class MarketThemeStockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mapping_id: int
    theme_id: int
    stock_id: int
    stock_code: str
    stock_name: str
    market: str | None
    mapping_source: str
    confidence_score: float | None
    is_primary: int
    is_active: int
    supply_day_count: int = 0
    recent_30d_supply_day_count: int = 0
    first_supply_date: str | None = None
    last_supply_date: str | None = None
    created_at: str
    updated_at: str


class MarketThemeStockSupplyCurrentTheme(BaseModel):
    theme_id: int
    theme_name: str
    color: str = "#dc2626"


class MarketThemeStockLinkedThemeSupplySummary(BaseModel):
    theme_id: int
    theme_name: str
    supply_count: int = 0
    supply_dates: list[str] = Field(default_factory=list)
    is_current_theme: bool = False


class MarketThemeStockSupplyMemoItem(BaseModel):
    detected_date: str
    memo: str
    source: str | None = None
    is_current_theme_supply_date: bool = False

class MarketThemeStockSupplySummaryResponse(BaseModel):
    theme_id: int
    theme_name: str
    stock_id: int
    stock_code: str
    stock_name: str
    supply_day_count: int = 0
    recent_30d_supply_day_count: int = 0
    first_supply_date: str | None = None
    last_supply_date: str | None = None
    all_theme_supply_day_count: int = 0
    recent_supply_dates: list[str] = Field(default_factory=list)
    current_theme: MarketThemeStockSupplyCurrentTheme
    linked_theme_supply_summaries: list[MarketThemeStockLinkedThemeSupplySummary] = Field(default_factory=list)
    period_start_date: str
    period_end_date: str
    recent_30d_theme_supply_count: int = 0
    current_theme_supply_count: int = 0
    overall_stock_supply_count: int = 0
    latest_current_theme_supply_date: str | None = None
    first_current_theme_supply_date: str | None = None
    current_theme_supply_dates: list[str] = Field(default_factory=list)
    overall_stock_supply_dates: list[str] = Field(default_factory=list)
    stock_memos: list[MarketThemeStockSupplyMemoItem] = Field(default_factory=list)


class MarketThemeByStockItem(BaseModel):
    theme_id: int
    theme_name: str
    is_primary: bool


class MarketThemeByStockResponse(BaseModel):
    stock_code: str
    stock_name: str | None
    themes: list[MarketThemeByStockItem]


class MarketThemeStockMemoItem(BaseModel):
    memo_date: str
    memo: str
    source: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class MarketThemeStockMemoResponse(BaseModel):
    stock_code: str
    stock_name: str | None = None
    items: list[MarketThemeStockMemoItem]
