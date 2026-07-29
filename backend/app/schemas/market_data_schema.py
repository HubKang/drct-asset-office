from __future__ import annotations

from pydantic import BaseModel, Field


class MarketDataCollectItem(BaseModel):
    item_type: str
    item_code: str


class MarketDataCollectRequest(BaseModel):
    mode: str = "SELECTED"
    items: list[MarketDataCollectItem] | None = None
    triggered_by: str | None = "USER"
    start_date: str | None = None
    end_date: str | None = None


class MarketDataCollectItemResult(BaseModel):
    item_type: str
    item_code: str
    provider_code: str | None = None
    status: str
    requested_from: str | None = None
    requested_to: str | None = None
    received_count: int = 0
    inserted_count: int = 0
    updated_count: int = 0
    unchanged_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    error_type: str | None = None
    error_message: str | None = None
    elapsed_ms: int = 0


class MarketDataCollectResponse(BaseModel):
    run_id: int
    run_type: str
    status: str
    target_count: int
    success_count: int = 0
    waiting_count: int = 0
    inserted_count: int = 0
    updated_count: int = 0
    unchanged_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    elapsed_ms: int = 0
    message: str
    results: list[MarketDataCollectItemResult] = Field(default_factory=list)


class MarketDataCollectionRun(BaseModel):
    id: int
    run_type: str
    status: str
    started_at: str
    finished_at: str | None = None
    target_count: int = 0
    success_count: int = 0
    inserted_count: int = 0
    updated_count: int = 0
    unchanged_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    elapsed_ms: int = 0
    triggered_by: str | None = None
    error_summary: str | None = None


class MarketDataCollectionRunItem(BaseModel):
    id: int
    run_id: int
    item_type: str
    item_code: str
    provider_code: str | None = None
    status: str
    requested_from: str | None = None
    requested_to: str | None = None
    received_count: int = 0
    inserted_count: int = 0
    updated_count: int = 0
    unchanged_count: int = 0
    http_status: int | None = None
    provider_error_code: str | None = None
    error_type: str | None = None
    error_message: str | None = None
    retry_count: int = 0
    elapsed_ms: int = 0


class MarketDataCollectionRunListResponse(BaseModel):
    items: list[MarketDataCollectionRun] = Field(default_factory=list)


class MarketDataCollectionRunItemListResponse(BaseModel):
    items: list[MarketDataCollectionRunItem] = Field(default_factory=list)
