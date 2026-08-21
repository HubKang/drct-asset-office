from __future__ import annotations

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class UsThemeGroup(Base):
    __tablename__ = "us_theme_groups"
    __table_args__ = (UniqueConstraint("name", name="uq_us_theme_groups_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class UsTheme(Base):
    __tablename__ = "us_themes"
    __table_args__ = (
        UniqueConstraint("theme_group_id", "name", name="uq_us_themes_group_name"),
        Index("idx_us_themes_group_active", "theme_group_id", "active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    theme_group_id: Mapped[int] = mapped_column(ForeignKey("us_theme_groups.id", ondelete="RESTRICT"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class UsThemeStock(Base):
    __tablename__ = "us_theme_stocks"
    __table_args__ = (
        UniqueConstraint("theme_id", "us_stock_id", name="uq_us_theme_stocks_theme_stock"),
        CheckConstraint("role IN ('LEADER','CORE','RELATED','ETF')", name="ck_us_theme_stocks_role"),
        Index("idx_us_theme_stocks_theme_active", "theme_id", "active"),
        Index("idx_us_theme_stocks_stock_active", "us_stock_id", "active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    theme_id: Mapped[int] = mapped_column(ForeignKey("us_themes.id", ondelete="CASCADE"), nullable=False)
    us_stock_id: Mapped[int] = mapped_column(ForeignKey("us_stocks.id", ondelete="RESTRICT"), nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="RELATED")
    is_representative: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class UsThemeDailyReturn(Base):
    __tablename__ = "us_theme_daily_returns"
    __table_args__ = (
        UniqueConstraint("theme_id", "trade_date", name="uq_us_theme_daily_returns_theme_date"),
        Index("idx_us_theme_daily_returns_date", "trade_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    theme_id: Mapped[int] = mapped_column(ForeignKey("us_themes.id", ondelete="CASCADE"), nullable=False)
    trade_date: Mapped[str] = mapped_column(Text, nullable=False)
    simple_return: Mapped[float] = mapped_column(Float, nullable=False)
    theme_strength: Mapped[float] = mapped_column(Float, nullable=False)
    trimmed_mean_return: Mapped[float] = mapped_column(Float, nullable=False)
    median_return: Mapped[float] = mapped_column(Float, nullable=False)
    breadth_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    valid_stock_count: Mapped[int] = mapped_column(Integer, nullable=False)
    up_count: Mapped[int] = mapped_column(Integer, nullable=False)
    down_count: Mapped[int] = mapped_column(Integer, nullable=False)
    flat_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
