from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class NewsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_id: int | None
    stock_code: str | None = None
    stock_name: str | None = None
    title: str
    source: str | None
    url: str | None
    published_at: str | None
    collected_at: str
    raw_text_path: str | None
    summary: str | None
    sentiment: str | None
    importance_score: int
    ai_summary: str | None
    ai_sentiment: str | None
    ai_importance_score: int | None
    ai_tags: str | None
    ai_processed_at: str | None
    ai_summary_error: str | None
    created_at: str
