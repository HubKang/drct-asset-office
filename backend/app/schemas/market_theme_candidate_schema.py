from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class MarketThemeCandidateListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    theme_id: int
    theme_name: str
    stock_id: int
    stock_code: str
    stock_name: str
    candidate_source: str
    confidence_score: float | None
    matched_keywords: list[str]
    evidence_count: int
    evidence_summary: str | None
    status: str
    review_memo: str | None
    reviewed_at: str | None
    created_at: str
    updated_at: str


class MarketThemeCandidateGenerateRequest(BaseModel):
    lookback_days: int = 7
    source: str = "all"
    limit: int = 500
    force: bool = False


class MarketThemeCandidateGenerateResponse(BaseModel):
    generated_count: int
    updated_count: int
    skipped_existing_mapping_count: int
    skipped_rejected_count: int
    source: str
    lookback_days: int


class MarketThemeCandidateReviewRequest(BaseModel):
    review_memo: str | None = None


class MarketThemeCandidateApproveResponse(BaseModel):
    candidate: MarketThemeCandidateListResponse
    mapping_id: int
    message: str

