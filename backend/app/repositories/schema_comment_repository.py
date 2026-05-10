from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from backend.app.entities.schema_comment import SchemaComment


class SchemaCommentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self, table_name: str | None) -> list[SchemaComment]:
        stmt: Select[tuple[SchemaComment]] = select(SchemaComment)
        if table_name:
            stmt = stmt.where(SchemaComment.table_name == table_name)
        stmt = stmt.order_by(SchemaComment.table_name.asc(), SchemaComment.column_name.asc())
        return list(self.db.scalars(stmt).all())
