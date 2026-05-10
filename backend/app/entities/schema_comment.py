from __future__ import annotations

from sqlalchemy import Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class SchemaComment(Base):
    __tablename__ = "schema_comments"
    __table_args__ = (UniqueConstraint("table_name", "column_name", name="uq_schema_comments_table_column"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_name: Mapped[str] = mapped_column(Text, nullable=False)
    column_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    comment_ko: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
