from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.repositories.news_repository import NewsRepository
from backend.app.schemas.news_schema import NewsResponse


class NewsService:
    def __init__(self, db: Session) -> None:
        self.repo = NewsRepository(db)

    def list_news(self, stock_id: int | None, keyword: str | None, source: str | None, limit: int, offset: int):
        rows = self.repo.list_with_stock(stock_id=stock_id, keyword=keyword, source=source, limit=limit, offset=offset)
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

    def get_news(self, news_id: int):
        item = self.repo.get_by_id(news_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="news not found")
        return item
