from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.entities.schema_comment import SchemaComment
from backend.app.repositories.schema_comment_repository import SchemaCommentRepository


class SchemaCommentService:
    def __init__(self, db: Session) -> None:
        self.repo = SchemaCommentRepository(db)

    def list_comments(self, table_name: str | None) -> list[SchemaComment]:
        return self.repo.list(table_name=table_name)
