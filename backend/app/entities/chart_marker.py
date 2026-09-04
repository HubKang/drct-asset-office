from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base
from backend.app.entities.stock import Stock  # noqa: F401 - registers the FK target in Base.metadata


class ChartMarkerGroup(Base):
    __tablename__ = "chart_marker_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str] = mapped_column(String(20), nullable=False, default="#64748b")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)


class ChartMarkerGroupKnowledgeLink(Base):
    __tablename__ = "chart_marker_group_knowledge_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    marker_group_id: Mapped[int] = mapped_column(ForeignKey("chart_marker_groups.id", ondelete="CASCADE"), nullable=False)
    # KMS tables are managed through explicit SQL rather than SQLAlchemy metadata.
    # The database migration/runtime schema adds the durable FK to kms_knowledge_items.
    knowledge_item_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)

    __table_args__ = (
        UniqueConstraint("marker_group_id", "knowledge_item_id", name="uq_chart_marker_group_knowledge"),
    )


class ChartMarker(Base):
    __tablename__ = "chart_markers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    marker_group_id: Mapped[int] = mapped_column(ForeignKey("chart_marker_groups.id", ondelete="RESTRICT"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    symbol: Mapped[str] = mapped_column(String(12), nullable=False, default="◆")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (UniqueConstraint("marker_group_id", "name", name="uq_chart_marker_group_name"),)


class ChartMarkerEvent(Base):
    __tablename__ = "chart_marker_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    marker_id: Mapped[int] = mapped_column(ForeignKey("chart_markers.id", ondelete="RESTRICT"), nullable=False)
    marker_date: Mapped[date] = mapped_column(Date, nullable=False)
    memo: Mapped[str | None] = mapped_column(Text)
    review_result: Mapped[str | None] = mapped_column(String(20))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint("stock_id", "marker_id", "marker_date", name="uq_chart_marker_event"),
        CheckConstraint("review_result IS NULL OR review_result IN ('S', 'F')", name="ck_chart_marker_event_review_result"),
    )


class ChartMarkerLearningDecision(Base):
    """A curator's explicit inclusion decision; computed learning detail stays transient."""

    __tablename__ = "chart_marker_learning_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chart_marker_event_id: Mapped[int] = mapped_column(
        ForeignKey("chart_marker_events.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    decision: Mapped[str] = mapped_column(String(10), nullable=False)
    decision_reason: Mapped[str | None] = mapped_column(String(120))
    pattern_algorithm_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        CheckConstraint("decision IN ('INCLUDE', 'EXCLUDE')", name="ck_chart_marker_learning_decision"),
    )
