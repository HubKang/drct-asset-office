from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.trade_review_schema import (
    TradeReviewDetailResponse,
    TradeReviewGptPackageResponse,
    TradeReviewListResponse,
    TradeReviewSaveRequest,
    TradeReviewSummaryResponse,
)
from backend.app.services.trade_review_service import TradeReviewService

router = APIRouter(tags=["trade-reviews"])


@router.get("/trade-reviews", response_model=TradeReviewListResponse)
def list_trade_reviews(
    from_date: str | None = None,
    to_date: str | None = None,
    review_status: str | None = None,
    trade_grade: str | None = None,
    result_type: str | None = None,
    method_id: int | None = None,
    stock_name: str | None = None,
    main_mistake: str | None = None,
    impulse_trade: bool | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return TradeReviewService(db).list_reviews(
        from_date=from_date,
        to_date=to_date,
        review_status=review_status,
        trade_grade=trade_grade,
        result_type=result_type,
        method_id=method_id,
        stock_name=stock_name,
        main_mistake=main_mistake,
        impulse_trade=impulse_trade,
        limit=limit,
        offset=offset,
    )


@router.get("/trade-reviews/summary", response_model=TradeReviewSummaryResponse)
def summarize_trade_reviews(
    from_date: str | None = None,
    to_date: str | None = None,
    db: Session = Depends(get_db),
):
    return TradeReviewService(db).summarize(from_date=from_date, to_date=to_date)


@router.get("/trade-reviews/{journal_id}", response_model=TradeReviewDetailResponse)
def get_trade_review(journal_id: int, db: Session = Depends(get_db)):
    return TradeReviewService(db).get_detail(journal_id)


@router.get("/trade-reviews/{journal_id}/gpt-package", response_model=TradeReviewGptPackageResponse)
def get_trade_review_gpt_package(journal_id: int, db: Session = Depends(get_db)):
    return TradeReviewService(db).build_gpt_review_package(journal_id)


@router.post("/trade-reviews/{journal_id}", response_model=TradeReviewDetailResponse)
def save_trade_review(journal_id: int, payload: TradeReviewSaveRequest, db: Session = Depends(get_db)):
    return TradeReviewService(db).save_review(journal_id, payload)
