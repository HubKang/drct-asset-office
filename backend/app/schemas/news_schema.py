from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class NewsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_id: int | None
    stock_code: str | None = None
    stock_name: str | None = None
    title: str
    url: str | None
    published_at: str | None
    collected_at: str
    summary: str | None
    created_at: str


class NewsCollectionTargetResponse(BaseModel):
    stock_id: int
    stock_code: str
    stock_name: str
    news_count: int
    summarized_count: int
    latest_collected_at: str | None


class NewsListPageResponse(BaseModel):
    items: list[NewsResponse]
    total_count: int
    limit: int
    offset: int


class NewsBulkDeleteRequest(BaseModel):
    news_ids: list[int]


class NewsBulkDeleteResponse(BaseModel):
    deleted: int
    failed: int


class NewsSummarizeRequest(BaseModel):
    news_ids: list[int]


class NewsSummarizeResponse(BaseModel):
    requested: int
    summarized: int
    skipped_existing: int
    missing_url: int
    fetch_failed: int
    processing_failed: int
