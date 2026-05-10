from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.collector_schema import (
    CollectDisclosuresRequest,
    CollectNewsRequest,
    CollectWatchlistDisclosuresRequest,
    CollectWatchlistNewsRequest,
    CollectorResultResponse,
)
from backend.app.services.collector_service import CollectorService

router = APIRouter()


@router.post("/collectors/news", response_model=CollectorResultResponse)
def collect_news(payload: CollectNewsRequest, db: Session = Depends(get_db)) -> CollectorResultResponse:
    service = CollectorService(db)
    providers = payload.providers or ["naver"]
    return service.collect_news_for_stock(stock_id=payload.stock_id, providers=providers, display=payload.display, sort=payload.sort, keyword=payload.keyword)


@router.post("/collectors/news/watchlist", response_model=CollectorResultResponse)
def collect_news_watchlist(payload: CollectWatchlistNewsRequest, db: Session = Depends(get_db)) -> CollectorResultResponse:
    service = CollectorService(db)
    providers = payload.providers or ["naver"]
    return service.collect_news_for_watchlist(providers=providers, display=payload.display, sort=payload.sort)


@router.post("/collectors/disclosures", response_model=CollectorResultResponse)
def collect_disclosures(payload: CollectDisclosuresRequest, db: Session = Depends(get_db)) -> CollectorResultResponse:
    service = CollectorService(db)
    return service.collect_disclosures_for_stock(
        stock_id=payload.stock_id,
        days=payload.days,
        page_count=payload.page_count,
    )


@router.post("/collectors/disclosures/watchlist", response_model=CollectorResultResponse)
def collect_disclosures_watchlist(payload: CollectWatchlistDisclosuresRequest, db: Session = Depends(get_db)) -> CollectorResultResponse:
    service = CollectorService(db)
    return service.collect_disclosures_for_watchlist(
        days=payload.days,
        page_count=payload.page_count,
    )
