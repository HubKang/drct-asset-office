from __future__ import annotations

from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class GptPromptTemplate(Base):
    __tablename__ = "gpt_prompt_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(Text, nullable=False, default="common")
    prompt_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    prompt_name: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    default_prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
