from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class WatchlistEvaluationRun(Base):
    __tablename__ = "watchlist_evaluation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_date: Mapped[str] = mapped_column(Text, nullable=False)
    run_type: Mapped[str] = mapped_column(Text, nullable=False, default="MANUAL")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="SUCCESS")
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class WatchlistEvaluationScore(Base):
    __tablename__ = "watchlist_evaluation_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("watchlist_evaluation_runs.id", ondelete="CASCADE"), nullable=False)
    watchlist_stock_id: Mapped[int] = mapped_column(ForeignKey("watchlist.id", ondelete="CASCADE"), nullable=False)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    evaluated_at: Mapped[str] = mapped_column(Text, nullable=False)
    market_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    material_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    supply_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    chart_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    financial_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    material_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    supply_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    chart_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    financial_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    overall_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_confidence: Mapped[str] = mapped_column(Text, nullable=False, default="NOT_EVALUATED")
    risk_flags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    missing_data_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class WatchlistEvaluationFactor(Base):
    __tablename__ = "watchlist_evaluation_factors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    score_id: Mapped[int] = mapped_column(ForeignKey("watchlist_evaluation_scores.id", ondelete="CASCADE"), nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    factor_code: Mapped[str] = mapped_column(Text, nullable=False)
    factor_name: Mapped[str] = mapped_column(Text, nullable=False)
    raw_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    contribution_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_table: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
