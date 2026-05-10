from __future__ import annotations

from sqlalchemy import Select, not_, select
from sqlalchemy.orm import Session

from backend.app.entities.news import NewsItem


class NewsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, item: NewsItem) -> NewsItem:
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_by_id(self, news_id: int) -> NewsItem | None:
        return self.db.get(NewsItem, news_id)

    def get_by_url(self, url: str) -> NewsItem | None:
        return self.db.scalar(select(NewsItem).where(NewsItem.url == url))

    def list(self, stock_id: int | None, keyword: str | None, source: str | None, limit: int, offset: int) -> list[NewsItem]:
        stmt: Select[tuple[NewsItem]] = select(NewsItem)
        if stock_id is not None:
            stmt = stmt.where(NewsItem.stock_id == stock_id)
        if keyword:
            keyword_like = f"%{keyword}%"
            stmt = stmt.where((NewsItem.title.like(keyword_like)) | (NewsItem.summary.like(keyword_like)))
        if source:
            stmt = stmt.where(NewsItem.source == source)
        stmt = stmt.order_by(NewsItem.id.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt).all())

    def list_recent_by_stock(self, stock_id: int, limit: int) -> list[NewsItem]:
        stmt: Select[tuple[NewsItem]] = (
            select(NewsItem)
            .where(NewsItem.stock_id == stock_id)
            .order_by(NewsItem.id.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def list_by_ids(self, stock_id: int, ids: list[int]) -> list[NewsItem]:
        if not ids:
            return []
        stmt: Select[tuple[NewsItem]] = (
            select(NewsItem)
            .where(NewsItem.stock_id == stock_id, NewsItem.id.in_(ids))
            .order_by(NewsItem.id.desc())
        )
        return list(self.db.scalars(stmt).all())

    def list_by_ids_any(self, ids: list[int]) -> list[NewsItem]:
        if not ids:
            return []
        stmt: Select[tuple[NewsItem]] = select(NewsItem).where(NewsItem.id.in_(ids)).order_by(NewsItem.id.desc())
        return list(self.db.scalars(stmt).all())

    def list_recent_unused_by_stock(self, stock_id: int, exclude_ids: set[int], limit: int) -> list[NewsItem]:
        stmt: Select[tuple[NewsItem]] = select(NewsItem).where(NewsItem.stock_id == stock_id)
        if exclude_ids:
            stmt = stmt.where(not_(NewsItem.id.in_(exclude_ids)))
        stmt = stmt.order_by(NewsItem.id.desc()).limit(limit)
        return list(self.db.scalars(stmt).all())

    def list_for_ai_summary(
        self,
        stock_id: int | None = None,
        limit: int = 10,
        only_unprocessed: bool = True,
        overwrite: bool = False,
    ) -> list[NewsItem]:
        stmt: Select[tuple[NewsItem]] = select(NewsItem)
        if stock_id is not None:
            stmt = stmt.where(NewsItem.stock_id == stock_id)
        if only_unprocessed and not overwrite:
            stmt = stmt.where(NewsItem.ai_summary.is_(None))
        stmt = stmt.order_by(NewsItem.id.desc()).limit(limit)
        return list(self.db.scalars(stmt).all())

    def list_for_classification(self, stock_id: int | None = None, limit: int = 100) -> list[NewsItem]:
        stmt: Select[tuple[NewsItem]] = select(NewsItem).where(NewsItem.ai_summary.is_not(None))
        if stock_id is not None:
            stmt = stmt.where(NewsItem.stock_id == stock_id)
        stmt = stmt.order_by(NewsItem.id.desc()).limit(limit)
        return list(self.db.scalars(stmt).all())

    def update_ai_summary(
        self,
        news_id: int,
        ai_summary: str,
        ai_sentiment: str | None,
        ai_importance_score: int,
        ai_tags: str | None,
        ai_processed_at: str,
        ai_summary_error: str | None = None,
    ) -> None:
        item = self.get_by_id(news_id)
        if not item:
            return
        item.ai_summary = ai_summary
        item.ai_sentiment = ai_sentiment
        item.ai_importance_score = ai_importance_score
        item.ai_tags = ai_tags
        item.ai_processed_at = ai_processed_at
        item.ai_summary_error = ai_summary_error
        self.db.add(item)
        self.db.commit()

    def mark_ai_summary_failed(self, news_id: int, error_message: str, ai_processed_at: str) -> None:
        item = self.get_by_id(news_id)
        if not item:
            return
        item.ai_summary_error = error_message
        item.ai_processed_at = ai_processed_at
        self.db.add(item)
        self.db.commit()

    def bulk_create_skip_duplicates(self, items: list[NewsItem]) -> tuple[int, int]:
        saved = 0
        skipped = 0
        seen_urls: set[str] = set()
        for item in items:
            if item.url:
                if item.url in seen_urls or self.get_by_url(item.url):
                    skipped += 1
                    continue
                seen_urls.add(item.url)
            self.db.add(item)
            saved += 1
        self.db.commit()
        return saved, skipped
