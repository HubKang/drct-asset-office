from __future__ import annotations

from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class TradeReview(Base):
    __tablename__ = "trade_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    decision_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    review_date: Mapped[str] = mapped_column(Text, nullable=False)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    what_was_right: Mapped[str | None] = mapped_column(Text, nullable=True)
    what_was_wrong: Mapped[str | None] = mapped_column(Text, nullable=True)
    lesson_learned: Mapped[str | None] = mapped_column(Text, nullable=True)
    journal_id: Mapped[int] = mapped_column(Integer, nullable=False)
    method_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    review_status: Mapped[str] = mapped_column(Text, nullable=False, default="미복기")
    trade_grade: Mapped[str | None] = mapped_column(Text, nullable=True)
    principle_followed: Mapped[str | None] = mapped_column(Text, nullable=True)
    entry_quality: Mapped[str | None] = mapped_column(Text, nullable=True)
    exit_quality: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_control_quality: Mapped[str | None] = mapped_column(Text, nullable=True)
    emotion_control_quality: Mapped[str | None] = mapped_column(Text, nullable=True)
    impulse_trade: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    main_mistake: Mapped[str | None] = mapped_column(Text, nullable=True)
    good_point: Mapped[str | None] = mapped_column(Text, nullable=True)
    improvement_point: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    gpt_review_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str | None] = mapped_column(Text, nullable=True)
