from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class MarketTheme(Base):
    __tablename__ = "market_themes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    theme_name: Mapped[str] = mapped_column(Text, nullable=False)
    theme_code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    theme_type: Mapped[str] = mapped_column(Text, nullable=False)
    theme_level: Mapped[str] = mapped_column(Text, nullable=False, default="THEME")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    parent_theme_id: Mapped[int | None] = mapped_column(ForeignKey("market_themes.id"), nullable=True)
    is_supply_theme: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
