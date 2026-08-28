from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class NewsItem(Base):
    __tablename__ = "news_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_id: Mapped[int | None] = mapped_column(ForeignKey("stocks.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    article_fingerprint: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    collected_at: Mapped[str] = mapped_column(Text, nullable=False)
    raw_text_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentiment: Mapped[str | None] = mapped_column(Text, nullable=True)
    importance_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_sentiment: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_importance_score: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    ai_tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_processed_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_summary_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class NewsItemExclusion(Base):
    __tablename__ = "news_item_exclusions"

    target_date: Mapped[str] = mapped_column(Text, primary_key=True)
    stock_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_fingerprint: Mapped[str] = mapped_column(Text, primary_key=True)


class NewsCollectionCursor(Base):
    __tablename__ = "news_collection_cursors"

    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"), primary_key=True)
    last_completed_date: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
