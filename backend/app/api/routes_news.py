from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.news_schema import NewsCollectionTargetResponse, NewsResponse
from backend.app.services.news_service import NewsService

router = APIRouter()


@router.get("/news", response_model=list[NewsResponse])
def list_news(
    stock_id: int | None = None,
    stock_ids: str | None = None,
    keyword: str | None = None,
    source: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[NewsResponse]:
    parsed_stock_ids: list[int] | None = None
    if stock_ids:
        parsed_stock_ids = [int(value.strip()) for value in stock_ids.split(",") if value.strip().isdigit()]
        if not parsed_stock_ids:
            parsed_stock_ids = None
    return NewsService(db).list_news(
        stock_id=stock_id,
        stock_ids=parsed_stock_ids,
        keyword=keyword,
        source=source,
        limit=limit,
        offset=offset,
    )


@router.get("/news/collection-targets", response_model=list[NewsCollectionTargetResponse])
def list_news_collection_targets(db: Session = Depends(get_db)) -> list[NewsCollectionTargetResponse]:
    return NewsService(db).list_collection_targets()


@router.get("/news/{news_id}", response_model=NewsResponse)
def get_news(news_id: int, db: Session = Depends(get_db)) -> NewsResponse:
    return NewsService(db).get_news(news_id)
