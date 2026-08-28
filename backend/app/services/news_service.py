from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.repositories.news_repository import NewsRepository
from backend.app.schemas.news_schema import (
    NewsCollectionTargetResponse,
    NewsListPageResponse,
    NewsResponse,
    NewsSummarizeResponse,
)
from backend.app.services.telegram_article_service import TelegramArticleService
from backend.app.services.telegram_llm_service import TelegramLLMService


class NewsService:
    def __init__(self, db: Session) -> None:
        self.repo = NewsRepository(db)
        self.article_service = TelegramArticleService()
        self.llm_service: TelegramLLMService | None = None

    def list_news(
        self, stock_id: int | None, stock_ids: list[int] | None, keyword: str | None,
        summary_status: str | None, limit: int, offset: int,
    ) -> list[NewsResponse]:
        rows = self.repo.list_with_stock(
            stock_id=stock_id, stock_ids=stock_ids, keyword=keyword,
            summary_status=summary_status, limit=limit, offset=offset,
        )
        return [NewsResponse.model_validate({
            **news.__dict__,
            "stock_code": stock.stock_code if stock else None,
            "stock_name": stock.stock_name if stock else None,
        }) for news, stock in rows]

    def list_news_page(
        self, stock_id: int | None, stock_ids: list[int] | None, keyword: str | None,
        summary_status: str | None, limit: int, offset: int,
    ) -> NewsListPageResponse:
        items = self.list_news(stock_id, stock_ids, keyword, summary_status, limit, offset)
        total_count = self.repo.count(stock_id, stock_ids, keyword, summary_status)
        return NewsListPageResponse(items=items, total_count=total_count, limit=limit, offset=offset)

    def list_collection_targets(self) -> list[NewsCollectionTargetResponse]:
        rows = self.repo.list_collection_targets()
        return [NewsCollectionTargetResponse(
            stock_id=stock_id, stock_code=stock_code, stock_name=stock_name,
            news_count=int(news_count or 0), summarized_count=int(summarized_count or 0),
            latest_collected_at=latest_collected_at,
        ) for stock_id, stock_code, stock_name, news_count, summarized_count, latest_collected_at in rows]

    def get_news(self, news_id: int) -> NewsResponse:
        row = self.repo.get_with_stock(news_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="news not found")
        item, stock = row
        return NewsResponse.model_validate({
            **item.__dict__,
            "stock_code": stock.stock_code if stock else None,
            "stock_name": stock.stock_name if stock else None,
        })

    def delete_news_bulk(self, news_ids: list[int]) -> tuple[int, int]:
        selected = sorted(set(int(value) for value in news_ids if isinstance(value, int) and value > 0))
        if not selected:
            return 0, 0
        target_date = datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()
        deleted = self.repo.delete_by_ids_with_exclusion(selected, target_date)
        return deleted, max(0, len(selected) - deleted)

    def summarize_news(self, news_ids: list[int]) -> NewsSummarizeResponse:
        selected = list(dict.fromkeys(int(value) for value in news_ids if isinstance(value, int) and value > 0))[:20]
        rows = self.repo.list_by_ids_any(selected)
        totals = {"requested": len(selected), "summarized": 0, "skipped_existing": 0,
                  "missing_url": 0, "fetch_failed": 0, "processing_failed": 0}
        for item in rows:
            if item.summary and item.summary.strip():
                totals["skipped_existing"] += 1
                continue
            if not item.url:
                totals["missing_url"] += 1
                continue
            article_text = self.article_service.fetch_text(item.url)
            if not article_text:
                totals["fetch_failed"] += 1
                continue
            if self.llm_service is None:
                self.llm_service = TelegramLLMService()
            result = self.llm_service.summarize_article(article_text, item.title)
            if not result.get("success") or not result.get("summary"):
                totals["processing_failed"] += 1
                continue
            try:
                self.repo.update_summary(item, str(result["summary"]))
                totals["summarized"] += 1
            except Exception:
                self.repo.db.rollback()
                totals["processing_failed"] += 1
        totals["processing_failed"] += max(0, len(selected) - len(rows))
        return NewsSummarizeResponse(**totals)
