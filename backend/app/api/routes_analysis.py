from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi import Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.analysis_schema import (
    AiSummarizeResponse,
    ClassificationRequest,
    ClassificationResponse,
    DisclosureAiSummarizeRequest,
    NewsAiSummarizeRequest,
    SourceItemsClassificationRequest,
    SourceItemsAiSummarizeRequest,
    StockBriefingCandidateResponse,
    StockBriefingRequest,
    StockBriefingResponse,
)
from backend.app.services.analysis_service import AnalysisService

router = APIRouter()


@router.post("/analysis/stock-briefing", response_model=StockBriefingResponse)
def generate_stock_briefing(payload: StockBriefingRequest, db: Session = Depends(get_db)) -> StockBriefingResponse:
    return AnalysisService(db).generate_stock_briefing(
        stock_id=payload.stock_id,
        mode=payload.mode,
        news_limit=payload.news_limit,
        disclosure_limit=payload.disclosure_limit,
        chunk_size=payload.chunk_size,
        news_ids=payload.news_ids,
        disclosure_ids=payload.disclosure_ids,
    )


@router.get("/analysis/stock-briefing/candidates", response_model=StockBriefingCandidateResponse)
def get_stock_briefing_candidates(
    stock_id: int,
    news_limit: int = Query(default=20, ge=1, le=200),
    disclosure_limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> StockBriefingCandidateResponse:
    return AnalysisService(db).get_stock_briefing_candidates(
        stock_id=stock_id,
        news_limit=news_limit,
        disclosure_limit=disclosure_limit,
    )


@router.post("/analysis/news/ai-summarize", response_model=AiSummarizeResponse)
def summarize_news_items(payload: NewsAiSummarizeRequest, db: Session = Depends(get_db)) -> AiSummarizeResponse:
    return AnalysisService(db).summarize_news_items(
        stock_id=payload.stock_id,
        news_ids=payload.news_ids,
        limit=payload.limit,
        only_unprocessed=payload.only_unprocessed,
        overwrite=payload.overwrite,
    )


@router.post("/analysis/disclosures/ai-summarize", response_model=AiSummarizeResponse)
def summarize_disclosures(payload: DisclosureAiSummarizeRequest, db: Session = Depends(get_db)) -> AiSummarizeResponse:
    return AnalysisService(db).summarize_disclosures(
        stock_id=payload.stock_id,
        disclosure_ids=payload.disclosure_ids,
        limit=payload.limit,
        only_unprocessed=payload.only_unprocessed,
        overwrite=payload.overwrite,
    )


@router.post("/analysis/source-items/ai-summarize", response_model=AiSummarizeResponse)
def summarize_source_items(payload: SourceItemsAiSummarizeRequest, db: Session = Depends(get_db)) -> AiSummarizeResponse:
    return AnalysisService(db).summarize_source_items(
        stock_id=payload.stock_id,
        news_limit=payload.news_limit,
        disclosure_limit=payload.disclosure_limit,
        only_unprocessed=payload.only_unprocessed,
        overwrite=payload.overwrite,
    )


@router.post("/analysis/news/classify", response_model=ClassificationResponse)
def classify_news(payload: ClassificationRequest, db: Session = Depends(get_db)) -> ClassificationResponse:
    return AnalysisService(db).classify_news_items(stock_id=payload.stock_id, limit=payload.limit)


@router.post("/analysis/disclosures/classify", response_model=ClassificationResponse)
def classify_disclosures(payload: ClassificationRequest, db: Session = Depends(get_db)) -> ClassificationResponse:
    return AnalysisService(db).classify_disclosures(stock_id=payload.stock_id, limit=payload.limit)


@router.post("/analysis/source-items/classify", response_model=ClassificationResponse)
def classify_source_items(payload: SourceItemsClassificationRequest, db: Session = Depends(get_db)) -> ClassificationResponse:
    return AnalysisService(db).classify_source_items(
        stock_id=payload.stock_id,
        news_limit=payload.news_limit,
        disclosure_limit=payload.disclosure_limit,
    )
