from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class StockBriefingRequest(BaseModel):
    stock_id: int
    mode: Literal["incremental", "full", "selected"] = "incremental"
    news_limit: int = Field(default=20, ge=1, le=200)
    disclosure_limit: int = Field(default=20, ge=1, le=200)
    chunk_size: int = Field(default=5, ge=1, le=50)
    news_ids: list[int] | None = None
    disclosure_ids: list[int] | None = None


class StockBriefingResponse(BaseModel):
    status: str
    stock_id: int
    report_id: int
    markdown_path: str
    used_news_count: int
    used_disclosure_count: int
    chunk_count: int
    message: str


class StockBriefingCandidateNewsItem(BaseModel):
    id: int
    title: str
    published_at: str | None
    summary: str | None
    source: str | None
    url: str | None
    used_in_report: bool


class StockBriefingCandidateDisclosureItem(BaseModel):
    id: int
    disclosure_title: str
    disclosure_type: str | None
    disclosed_at: str | None
    url: str | None
    used_in_report: bool


class StockBriefingCandidateCounts(BaseModel):
    news_total: int
    news_unused: int
    disclosure_total: int
    disclosure_unused: int


class StockBriefingCandidateResponse(BaseModel):
    stock_id: int
    stock_code: str
    stock_name: str
    news: list[StockBriefingCandidateNewsItem]
    disclosures: list[StockBriefingCandidateDisclosureItem]
    counts: StockBriefingCandidateCounts


class NewsAiSummarizeRequest(BaseModel):
    stock_id: int | None = None
    news_ids: list[int] | None = None
    limit: int = Field(default=10, ge=1, le=500)
    only_unprocessed: bool = True
    overwrite: bool = False


class DisclosureAiSummarizeRequest(BaseModel):
    stock_id: int | None = None
    disclosure_ids: list[int] | None = None
    limit: int = Field(default=10, ge=1, le=500)
    only_unprocessed: bool = True
    overwrite: bool = False


class SourceItemsAiSummarizeRequest(BaseModel):
    stock_id: int | None = None
    news_limit: int = Field(default=10, ge=1, le=500)
    disclosure_limit: int = Field(default=10, ge=1, le=500)
    only_unprocessed: bool = True
    overwrite: bool = False


class AiSummarizeResponse(BaseModel):
    status: str
    target: str | None
    processed_count: int
    success_count: int
    failed_count: int
    skipped_count: int
    message: str


class ClassificationRequest(BaseModel):
    stock_id: int | None = None
    limit: int = Field(default=100, ge=1, le=1000)


class SourceItemsClassificationRequest(BaseModel):
    stock_id: int | None = None
    news_limit: int = Field(default=100, ge=1, le=1000)
    disclosure_limit: int = Field(default=100, ge=1, le=1000)


class ClassificationResponse(BaseModel):
    status: str
    target: str
    processed_count: int
    message: str
