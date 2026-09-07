from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base
from backend.app.entities.chart_marker import ChartMarker  # noqa: F401 - registers the FK target


class DrctSignalSearch(Base):
    __tablename__ = "drct_signal_searches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    search_key: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    lifecycle_status: Mapped[str] = mapped_column(String(20), nullable=False, default="REFERENCE")
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        CheckConstraint(
            "lifecycle_status IN ('REFERENCE','LEARNING','SHADOW','ACTIVE','INACTIVE')",
            name="ck_drct_signal_search_lifecycle",
        ),
        Index("idx_drct_signal_searches_order", "display_order", "id"),
    )


class DrctSignalSearchVersion(Base):
    __tablename__ = "drct_signal_search_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    search_id: Mapped[int] = mapped_column(ForeignKey("drct_signal_searches.id", ondelete="RESTRICT"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    hts_reference_conditions: Mapped[str] = mapped_column(Text, nullable=False)
    hts_condition_expression: Mapped[str] = mapped_column(Text, nullable=False)
    drct_rule_text: Mapped[str | None] = mapped_column(Text)
    change_note: Mapped[str | None] = mapped_column(Text)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)

    __table_args__ = (
        UniqueConstraint("search_id", "version_no", name="uq_drct_signal_search_version"),
        Index("idx_drct_signal_search_versions_search", "search_id", "version_no"),
        Index("uq_drct_signal_search_current_version", "search_id", unique=True, sqlite_where=text("is_current = 1")),
    )


class DrctSignalSearchMarkerLink(Base):
    __tablename__ = "drct_signal_search_marker_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    search_id: Mapped[int] = mapped_column(ForeignKey("drct_signal_searches.id", ondelete="RESTRICT"), nullable=False)
    marker_definition_id: Mapped[int] = mapped_column(ForeignKey("chart_markers.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)

    __table_args__ = (
        UniqueConstraint("search_id", "marker_definition_id", name="uq_drct_signal_search_marker"),
        Index("idx_drct_signal_marker_links_marker", "marker_definition_id", "search_id"),
    )


class DrctSignalSearchRule(Base):
    __tablename__ = "drct_signal_search_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    search_version_id: Mapped[int] = mapped_column(
        ForeignKey("drct_signal_search_versions.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    rule_json: Mapped[str] = mapped_column(Text, nullable=False)
    validation_status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)

    __table_args__ = (
        CheckConstraint(
            "validation_status IN ('DRAFT','VALID','INVALID')",
            name="ck_drct_signal_rule_validation_status",
        ),
        Index("idx_drct_signal_rules_version", "search_version_id"),
    )


class DrctStockSignalEvent(Base):
    """A compact operational stock/marker signal episode and its observed outcome."""

    __tablename__ = "drct_stock_signal_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="RESTRICT"), nullable=False)
    marker_id: Mapped[int] = mapped_column(ForeignKey("chart_markers.id", ondelete="RESTRICT"), nullable=False)
    signal_date: Mapped[str] = mapped_column(Text, nullable=False)
    last_seen_date: Mapped[str] = mapped_column(Text, nullable=False)
    ended_date: Mapped[str | None] = mapped_column(Text)
    d0_close: Mapped[float] = mapped_column(Float, nullable=False)
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)
    similarity_percentile: Mapped[float | None] = mapped_column(Float)
    similarity_level: Mapped[str] = mapped_column(String(24), nullable=False)
    candidate_policy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    pattern_signature_version: Mapped[int] = mapped_column(Integer, nullable=False)
    feature_schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    improvement_candidate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    improvement_policy_version: Mapped[str | None] = mapped_column(String(64))
    evaluation_status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    d5_date: Mapped[str | None] = mapped_column(Text)
    d5_return_pct: Mapped[float | None] = mapped_column(Float)
    d10_date: Mapped[str | None] = mapped_column(Text)
    d10_return_pct: Mapped[float | None] = mapped_column(Float)
    d20_date: Mapped[str | None] = mapped_column(Text)
    d20_return_pct: Mapped[float | None] = mapped_column(Float)
    max_rise_20_pct: Mapped[float | None] = mapped_column(Float)
    max_fall_20_pct: Mapped[float | None] = mapped_column(Float)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        CheckConstraint(
            "evaluation_status IN ('PENDING','D5_READY','D10_READY','COMPLETE')",
            name="ck_drct_stock_signal_event_status",
        ),
        Index("idx_drct_stock_signal_events_date", "signal_date"),
        Index("idx_drct_stock_signal_events_pair", "stock_id", "marker_id", "signal_date"),
        Index("idx_drct_stock_signal_events_status", "evaluation_status"),
        Index(
            "uq_drct_stock_signal_events_active_pair", "stock_id", "marker_id", unique=True,
            sqlite_where=text("ended_date IS NULL"),
        ),
    )
