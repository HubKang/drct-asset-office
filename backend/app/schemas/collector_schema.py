from __future__ import annotations

from pydantic import BaseModel, Field


class CollectNewsRequest(BaseModel):
    stock_id: int
    keyword: str | None = None
    providers: list[str] = Field(default_factory=lambda: ["naver"])
    display: int = 20
    sort: str = "date"


class CollectWatchlistNewsRequest(BaseModel):
    providers: list[str] = Field(default_factory=lambda: ["naver"])
    display: int = 10
    sort: str = "date"


class CollectDisclosuresRequest(BaseModel):
    stock_id: int
    days: int = 30
    page_count: int = 100


class CollectWatchlistDisclosuresRequest(BaseModel):
    days: int = 30
    page_count: int = 100


class CollectorResultResponse(BaseModel):
    collector_name: str
    status: str
    target: str
    collected_count: int
    saved_count: int
    skipped_count: int
    message: str
