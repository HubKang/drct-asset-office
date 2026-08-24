from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class UsKrThemeLink(Base):
    __tablename__ = "us_kr_theme_links"
    __table_args__ = (
        UniqueConstraint("us_theme_id", name="uq_us_kr_theme_links_us_theme"),
        UniqueConstraint("kr_theme_id", name="uq_us_kr_theme_links_kr_theme"),
        Index("idx_us_kr_theme_links_active", "active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    us_theme_id: Mapped[int] = mapped_column(ForeignKey("us_themes.id", ondelete="RESTRICT"), nullable=False)
    kr_theme_id: Mapped[int] = mapped_column(ForeignKey("market_themes.id", ondelete="RESTRICT"), nullable=False)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
