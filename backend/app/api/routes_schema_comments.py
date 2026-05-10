from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.schema_comment_schema import SchemaCommentResponse
from backend.app.services.schema_comment_service import SchemaCommentService

router = APIRouter()


@router.get("/schema-comments", response_model=list[SchemaCommentResponse])
def list_schema_comments(table_name: str | None = None, db: Session = Depends(get_db)) -> list[SchemaCommentResponse]:
    rows = SchemaCommentService(db).list_comments(table_name=table_name)
    return [SchemaCommentResponse(table_name=r.table_name, column_name=r.column_name, comment_ko=r.comment_ko) for r in rows]
