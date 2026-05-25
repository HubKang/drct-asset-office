from __future__ import annotations

from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class TelegramDailySummary(Base):
    __tablename__ = "telegram_daily_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    summary_date: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_points_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    theme_mentions_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    stock_mentions_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_points_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    top_tags_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    top_event_types_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_type_stats_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    market_view: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_has_content: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    llm_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    elapsed_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str | None] = mapped_column(Text, nullable=True)
