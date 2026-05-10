from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StockCreate(BaseModel):
    stock_code: str
    stock_name: str
    market: str | None = None
    sector: str | None = None
    industry: str | None = None
    security_type: str | None = None


class StockUpdate(BaseModel):
    stock_name: str | None = None
    market: str | None = None
    sector: str | None = None
    industry: str | None = None
    security_type: str | None = None
    is_active: int | None = None


class StockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_code: str
    stock_name: str
    market: str | None
    sector: str | None
    industry: str | None
    isin_code: str | None
    corp_name: str | None
    corp_reg_no: str | None
    last_synced_at: str | None
    source: str | None
    security_type: str | None
    is_active: int
    created_at: str
    updated_at: str
