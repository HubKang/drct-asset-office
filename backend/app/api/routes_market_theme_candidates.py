from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.market_theme_candidate_schema import (
    MarketThemeCandidateApproveResponse,
    MarketThemeCandidateGenerateRequest,
    MarketThemeCandidateGenerateResponse,
    MarketThemeCandidateListResponse,
    MarketThemeCandidateReviewRequest,
)
from backend.app.services.market_theme_candidate_service import MarketThemeCandidateService

router = APIRouter()


@router.get("/market-theme-stock-candidates", response_model=list[MarketThemeCandidateListResponse])
def list_market_theme_stock_candidates(
    status: str | None = Query(default=None),
    theme_id: int | None = Query(default=None),
    stock_id: int | None = Query(default=None),
    candidate_source: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[MarketThemeCandidateListResponse]:
    return MarketThemeCandidateService(db).list_candidates(
        status=status,
        theme_id=theme_id,
        stock_id=stock_id,
        candidate_source=candidate_source,
        limit=limit,
        offset=offset,
    )


@router.post("/market-theme-stock-candidates/generate", response_model=MarketThemeCandidateGenerateResponse)
def generate_market_theme_stock_candidates(
    payload: MarketThemeCandidateGenerateRequest,
    db: Session = Depends(get_db),
) -> MarketThemeCandidateGenerateResponse:
    return MarketThemeCandidateService(db).generate_candidates(payload)


@router.post("/market-theme-stock-candidates/{candidate_id}/approve", response_model=MarketThemeCandidateApproveResponse)
def approve_market_theme_stock_candidate(candidate_id: int, db: Session = Depends(get_db)) -> MarketThemeCandidateApproveResponse:
    return MarketThemeCandidateService(db).approve_candidate(candidate_id)


@router.post("/market-theme-stock-candidates/{candidate_id}/reject", response_model=MarketThemeCandidateListResponse)
def reject_market_theme_stock_candidate(
    candidate_id: int,
    payload: MarketThemeCandidateReviewRequest,
    db: Session = Depends(get_db),
) -> MarketThemeCandidateListResponse:
    return MarketThemeCandidateService(db).review_candidate(candidate_id, "rejected", payload.review_memo)


@router.post("/market-theme-stock-candidates/{candidate_id}/ignore", response_model=MarketThemeCandidateListResponse)
def ignore_market_theme_stock_candidate(
    candidate_id: int,
    payload: MarketThemeCandidateReviewRequest,
    db: Session = Depends(get_db),
) -> MarketThemeCandidateListResponse:
    return MarketThemeCandidateService(db).review_candidate(candidate_id, "ignored", payload.review_memo)

