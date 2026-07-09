from __future__ import annotations
from typing import Any
from pydantic import BaseModel

class StockFinancialCollectRequest(BaseModel):
    stock_ids: list[int]

class StockFinancialCollectItem(BaseModel):
    stock_id: int
    stock_code: str
    status: str
    snapshot_saved: bool = False
    annual_rows_saved: int = 0
    quarterly_rows_saved: int = 0
    message: str | None = None

class StockFinancialCollectResponse(BaseModel):
    status: str
    target_count: int
    success_count: int
    partial_count: int
    failed_count: int
    skipped_count: int = 0
    items: list[StockFinancialCollectItem]

class StockFinancialDataResponse(BaseModel):
    stock_id: int
    financial_snapshot: dict[str, Any] = {}
    financial_annual_statements: list[dict[str, Any]] = []
    financial_quarterly_statements: list[dict[str, Any]] = []
    shareholder_snapshot: dict[str, Any] = {}
