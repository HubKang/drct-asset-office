from __future__ import annotations

from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class TelegramItem(Base):
    __tablename__ = "telegram_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    telegram_message_id: Mapped[int] = mapped_column(Integer, nullable=False)
    message_date: Mapped[str] = mapped_column(Text, nullable=False)
    message_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_text_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    item_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    publisher: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_type: Mapped[str] = mapped_column(Text, nullable=False, default="unknown")
    item_category: Mapped[str] = mapped_column(Text, nullable=False, default="기타")
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_points_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    tag: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    sentiment: Mapped[str] = mapped_column(Text, nullable=False, default="neutral")
    risk_level: Mapped[str] = mapped_column(Text, nullable=False, default="unknown")
    event_type: Mapped[str] = mapped_column(Text, nullable=False, default="기타")
    related_stock_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    related_stock_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    related_theme: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    summary_has_content: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    analysis_status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    collected_at: Mapped[str] = mapped_column(Text, nullable=False)
    summarized_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str | None] = mapped_column(Text, nullable=True)
