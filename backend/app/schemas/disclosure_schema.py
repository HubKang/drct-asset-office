from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class DisclosureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_id: int
    stock_code: str | None = None
    stock_name: str | None = None
    dart_receipt_no: str | None
    disclosure_title: str
    disclosure_type: str | None
    disclosed_at: str | None
    url: str | None
    raw_text_path: str | None
    summary: str | None
    importance_score: int
    ai_summary: str | None
    ai_importance_score: int | None
    ai_tags: str | None
    ai_risk_level: str | None
    ai_event_type: str | None
    ai_processed_at: str | None
    ai_summary_error: str | None
    created_at: str


class DisclosureBulkDeleteRequest(BaseModel):
    disclosure_ids: list[int]


class DisclosureBulkDeleteResponse(BaseModel):
    deleted: int
    failed: int


class DisclosureCollectionTargetResponse(BaseModel):
    stock_id: int
    stock_code: str
    stock_name: str
    disclosure_count: int
    summarized_count: int
    last_successful_collection_date: str | None = None
    last_successful_at: str | None = None
