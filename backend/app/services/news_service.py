from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.repositories.news_repository import NewsRepository
from backend.app.schemas.news_schema import NewsCollectionTargetResponse, NewsResponse


class NewsService:
    def __init__(self, db: Session) -> None:
        self.repo = NewsRepository(db)

    def list_news(self, stock_id: int | None, stock_ids: list[int] | None, keyword: str | None, source: str | None, limit: int, offset: int):
        rows = self.repo.list_with_stock(stock_id=stock_id, stock_ids=stock_ids, keyword=keyword, source=source, limit=limit, offset=offset)
        result: list[NewsResponse] = []
        for news, stock in rows:
            result.append(
                NewsResponse.model_validate(
                    {
                        **news.__dict__,
                        "stock_code": stock.stock_code if stock else None,
                        "stock_name": stock.stock_name if stock else None,
                    }
                )
            )
        return result

    def list_collection_targets(self) -> list[NewsCollectionTargetResponse]:
        rows = self.repo.list_collection_targets()
        return [
            NewsCollectionTargetResponse(
                stock_id=stock_id,
                stock_code=stock_code,
                stock_name=stock_name,
                news_count=int(news_count or 0),
                ai_processed_count=int(ai_processed_count or 0),
                latest_collected_at=latest_collected_at,
            )
            for stock_id, stock_code, stock_name, news_count, ai_processed_count, latest_collected_at in rows
        ]

    def get_news(self, news_id: int):
        item = self.repo.get_by_id(news_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="news not found")
        return item
