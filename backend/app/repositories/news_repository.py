from __future__ import annotations

from sqlalchemy import Select, case, delete, func, not_, or_, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from backend.app.entities.news import NewsCollectionCursor, NewsItem, NewsItemExclusion
from backend.app.entities.stock import Stock
from backend.app.entities.watchlist import Watchlist


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

    def get_with_stock(self, news_id: int) -> tuple[NewsItem, Stock | None] | None:
        return self.db.execute(
            select(NewsItem, Stock)
            .join(Stock, NewsItem.stock_id == Stock.id, isouter=True)
            .where(NewsItem.id == news_id)
        ).one_or_none()

    @staticmethod
    def _latest_news_order():
        """Order by the article time users see, with durable fallbacks for legacy rows."""
        return (
            func.coalesce(
                func.nullif(NewsItem.published_at, ""),
                func.nullif(NewsItem.collected_at, ""),
                NewsItem.created_at,
            ).desc(),
            NewsItem.id.desc(),
        )

    def list(self, stock_id: int | None, stock_ids: list[int] | None, keyword: str | None, summary_status: str | None, limit: int, offset: int) -> list[NewsItem]:
        stmt: Select[tuple[NewsItem]] = select(NewsItem)
        if stock_id is not None:
            stmt = stmt.where(NewsItem.stock_id == stock_id)
        elif stock_ids:
            stmt = stmt.where(NewsItem.stock_id.in_(stock_ids))
        if keyword:
            keyword_like = f"%{keyword}%"
            stmt = stmt.where((NewsItem.title.like(keyword_like)) | (NewsItem.summary.like(keyword_like)))
        if summary_status == "summarized":
            stmt = stmt.where(NewsItem.summary.is_not(None), func.trim(NewsItem.summary) != "")
        elif summary_status == "unsummarized":
            stmt = stmt.where(or_(NewsItem.summary.is_(None), func.trim(NewsItem.summary) == ""))
        stmt = stmt.order_by(*self._latest_news_order()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt).all())

    def list_with_stock(self, stock_id: int | None, stock_ids: list[int] | None, keyword: str | None, summary_status: str | None, limit: int, offset: int) -> list[tuple[NewsItem, Stock | None]]:
        stmt: Select[tuple[NewsItem, Stock | None]] = select(NewsItem, Stock).join(Stock, NewsItem.stock_id == Stock.id, isouter=True)
        if stock_id is not None:
            stmt = stmt.where(NewsItem.stock_id == stock_id)
        elif stock_ids:
            stmt = stmt.where(NewsItem.stock_id.in_(stock_ids))
        if keyword:
            keyword_like = f"%{keyword}%"
            stmt = stmt.where((NewsItem.title.like(keyword_like)) | (NewsItem.summary.like(keyword_like)))
        if summary_status == "summarized":
            stmt = stmt.where(NewsItem.summary.is_not(None), func.trim(NewsItem.summary) != "")
        elif summary_status == "unsummarized":
            stmt = stmt.where(or_(NewsItem.summary.is_(None), func.trim(NewsItem.summary) == ""))
        stmt = stmt.order_by(*self._latest_news_order()).limit(limit).offset(offset)
        return list(self.db.execute(stmt).all())

    def count(self, stock_id: int | None, stock_ids: list[int] | None, keyword: str | None, summary_status: str | None) -> int:
        stmt = select(func.count(NewsItem.id))
        if stock_id is not None:
            stmt = stmt.where(NewsItem.stock_id == stock_id)
        elif stock_ids:
            stmt = stmt.where(NewsItem.stock_id.in_(stock_ids))
        if keyword:
            keyword_like = f"%{keyword}%"
            stmt = stmt.where((NewsItem.title.like(keyword_like)) | (NewsItem.summary.like(keyword_like)))
        if summary_status == "summarized":
            stmt = stmt.where(NewsItem.summary.is_not(None), func.trim(NewsItem.summary) != "")
        elif summary_status == "unsummarized":
            stmt = stmt.where(or_(NewsItem.summary.is_(None), func.trim(NewsItem.summary) == ""))
        return int(self.db.scalar(stmt) or 0)

    def list_collection_targets(self) -> list[tuple[int, str, str, int, int, str | None]]:
        summarized_count = func.sum(case((
            NewsItem.summary.is_not(None) & (func.trim(NewsItem.summary) != ""), 1,
        ), else_=0))
        stmt = (
            select(
                Stock.id,
                Stock.stock_code,
                Stock.stock_name,
                func.count(NewsItem.id),
                summarized_count,
                func.coalesce(NewsCollectionCursor.last_completed_date, func.max(NewsItem.collected_at)),
            )
            .join(Watchlist, Watchlist.stock_id == Stock.id)
            .join(NewsItem, NewsItem.stock_id == Stock.id, isouter=True)
            .join(NewsCollectionCursor, NewsCollectionCursor.stock_id == Stock.id, isouter=True)
            .where(Watchlist.is_active == 1)
            .group_by(Stock.id, Stock.stock_code, Stock.stock_name, NewsCollectionCursor.last_completed_date)
            .order_by(Stock.stock_name.asc())
        )
        return list(self.db.execute(stmt).all())

    def get_collection_cursor(self, stock_id: int) -> str | None:
        row = self.db.get(NewsCollectionCursor, stock_id)
        return row.last_completed_date if row else None

    def update_collection_cursor(self, stock_id: int, completed_date: str, timestamp: str) -> None:
        row = self.db.get(NewsCollectionCursor, stock_id)
        if row:
            row.last_completed_date = completed_date
            row.updated_at = timestamp
        else:
            self.db.add(NewsCollectionCursor(
                stock_id=stock_id,
                last_completed_date=completed_date,
                created_at=timestamp,
                updated_at=timestamp,
            ))
        self.db.commit()

    def get_by_stock_and_fingerprint(self, stock_id: int, fingerprint: str) -> NewsItem | None:
        return self.db.scalar(select(NewsItem).where(
            NewsItem.stock_id == stock_id, NewsItem.article_fingerprint == fingerprint,
        ))

    def is_excluded(self, target_date: str, stock_id: int, fingerprint: str) -> bool:
        return self.db.get(NewsItemExclusion, (target_date, stock_id, fingerprint)) is not None

    def cleanup_exclusions(self, target_date: str) -> int:
        result = self.db.execute(delete(NewsItemExclusion).where(NewsItemExclusion.target_date != target_date))
        self.db.commit()
        return int(result.rowcount or 0)

    def update_summary(self, item: NewsItem, summary: str) -> None:
        item.summary = summary
        self.db.add(item)
        self.db.commit()

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
        seen_keys: set[tuple[int | None, str | None]] = set()
        for item in items:
            key = (item.stock_id, item.article_fingerprint)
            if item.article_fingerprint:
                if key in seen_keys or (
                    item.stock_id is not None
                    and self.get_by_stock_and_fingerprint(item.stock_id, item.article_fingerprint)
                ):
                    skipped += 1
                    continue
                seen_keys.add(key)
            self.db.add(item)
            saved += 1
        self.db.commit()
        return saved, skipped

    def delete_by_ids(self, ids: list[int]) -> int:
        if not ids:
            return 0
        stmt = select(NewsItem).where(NewsItem.id.in_(ids))
        items = list(self.db.scalars(stmt).all())
        for item in items:
            self.db.delete(item)
        self.db.commit()
        return len(items)

    def delete_by_ids_with_exclusion(self, ids: list[int], target_date: str) -> int:
        if not ids:
            return 0
        items = list(self.db.scalars(select(NewsItem).where(NewsItem.id.in_(ids))).all())
        try:
            for item in items:
                if item.stock_id is not None and item.article_fingerprint:
                    self.db.execute(sqlite_insert(NewsItemExclusion).values(
                        target_date=target_date,
                        stock_id=item.stock_id,
                        article_fingerprint=item.article_fingerprint,
                    ).on_conflict_do_nothing(index_elements=["target_date", "stock_id", "article_fingerprint"]))
                self.db.delete(item)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return len(items)
