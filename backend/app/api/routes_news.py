from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.news_schema import NewsResponse
from backend.app.services.news_service import NewsService

router = APIRouter()


@router.get("/news", response_model=list[NewsResponse])
def list_news(
    stock_id: int | None = None,
    keyword: str | None = None,
    source: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[NewsResponse]:
    return NewsService(db).list_news(stock_id=stock_id, keyword=keyword, source=source, limit=limit, offset=offset)


@router.get("/news/{news_id}", response_model=NewsResponse)
def get_news(news_id: int, db: Session = Depends(get_db)) -> NewsResponse:
    return NewsService(db).get_news(news_id)
