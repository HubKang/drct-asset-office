from __future__ import annotations

from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class TradeMethodImage(Base):
    __tablename__ = "trade_method_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_method_id: Mapped[int] = mapped_column(Integer, nullable=False)
    image_type: Mapped[str] = mapped_column(Text, nullable=False)
    image_path: Mapped[str] = mapped_column(Text, nullable=False)
    image_memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str | None] = mapped_column(Text, nullable=True)
