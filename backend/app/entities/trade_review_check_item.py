from __future__ import annotations

from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class TradeReviewCheckItem(Base):
    __tablename__ = "trade_review_check_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[int] = mapped_column(Integer, nullable=False)
    journal_id: Mapped[int] = mapped_column(Integer, nullable=False)
    method_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    item_type: Mapped[str] = mapped_column(Text, nullable=False)
    item_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    item_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_checked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_field: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str | None] = mapped_column(Text, nullable=True)
