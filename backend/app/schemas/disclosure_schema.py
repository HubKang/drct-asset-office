from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class DisclosureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_id: int
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
