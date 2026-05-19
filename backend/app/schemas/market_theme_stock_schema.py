from __future__ import annotations

from pydantic import BaseModel, ConfigDict


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
    created_at: str
    updated_at: str

