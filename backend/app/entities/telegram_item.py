from __future__ import annotations

from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class TelegramItem(Base):
    __tablename__ = "telegram_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    collection_date: Mapped[str] = mapped_column(Text, nullable=False)
    message_at: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class TelegramMessageExclusion(Base):
    __tablename__ = "telegram_message_exclusions"

    exclusion_date: Mapped[str] = mapped_column(Text, primary_key=True)
    message_fingerprint: Mapped[str] = mapped_column(Text, primary_key=True)
