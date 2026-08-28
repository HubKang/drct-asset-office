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


class CollectSelectedWatchlistNewsRequest(BaseModel):
    stock_ids: list[int] = Field(default_factory=list)
    providers: list[str] = Field(default_factory=lambda: ["naver"])
    display: int = 10
    sort: str = "date"


class CollectDisclosuresRequest(BaseModel):
    stock_id: int
    days: int = 30  # compatibility only; collection range is cursor-driven
    page_count: int = 100


class CollectWatchlistDisclosuresRequest(BaseModel):
    days: int = 30
    page_count: int = 100


class CollectSelectedWatchlistDisclosuresRequest(BaseModel):
    stock_ids: list[int] = Field(default_factory=list)
    days: int = 30
    page_count: int = 100


class CollectorResultResponse(BaseModel):
    collector_name: str
    status: str
    target: str
    collected_count: int
    saved_count: int
    skipped_count: int
    mode: str | None = None
    from_date: str | None = None
    to_date: str | None = None
    initial_window: str | None = None
    scanned_count: int = 0
    matched_count: int = 0
    name_mismatch_skipped: int = 0
    duplicate_skipped: int = 0
    excluded_skipped: int = 0
    invalid_skipped: int = 0
    message: str
    skip_reasons: dict[str, int] = Field(default_factory=dict)


class SelectedCollectorItemResult(BaseModel):
    stock_id: int
    stock_code: str
    stock_name: str
    normalized_stock_code: str | None = None
    corp_code: str | None = None
    status: str
    collected_count: int = 0
    saved_count: int = 0
    skipped_count: int = 0
    mode: str | None = None
    from_date: str | None = None
    to_date: str | None = None
    initial_window: str | None = None
    scanned_count: int = 0
    matched_count: int = 0
    name_mismatch_skipped: int = 0
    duplicate_skipped: int = 0
    excluded_skipped: int = 0
    invalid_skipped: int = 0
    message: str | None = None


class SelectedCollectorResultResponse(BaseModel):
    requested_count: int
    success_count: int
    failed_count: int
    skipped_count: int = 0
    message: str
    results: list[SelectedCollectorItemResult] = Field(default_factory=list)
