from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class Disclosure(Base):
    __tablename__ = "disclosures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    dart_receipt_no: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True)
    disclosure_title: Mapped[str] = mapped_column(Text, nullable=False)
    disclosure_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    disclosed_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_text_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    importance_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_importance_score: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    ai_tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_risk_level: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_event_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_processed_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_summary_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class DisclosureItemExclusion(Base):
    __tablename__ = "disclosure_item_exclusions"

    exclusion_date: Mapped[str] = mapped_column(Text, primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"), primary_key=True)
    rcept_no: Mapped[str] = mapped_column(Text, primary_key=True)


class StockDisclosureCollectionState(Base):
    __tablename__ = "stock_disclosure_collection_states"

    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"), primary_key=True)
    last_successful_collection_date: Mapped[str] = mapped_column(Text, nullable=False)
    last_successful_at: Mapped[str] = mapped_column(Text, nullable=False)
