from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.schema_comment_schema import (
    SchemaCommentColumnResponse,
    SchemaCommentResponse,
    SchemaCommentTableResponse,
)
from backend.app.services.schema_comment_service import SchemaCommentService

router = APIRouter()


@router.get("/schema-comments", response_model=list[SchemaCommentResponse])
def list_schema_comments(table_name: str | None = None, db: Session = Depends(get_db)) -> list[SchemaCommentResponse]:
    rows = SchemaCommentService(db).list_comments(table_name=table_name)
    return [SchemaCommentResponse(table_name=r.table_name, column_name=r.column_name, comment_ko=r.comment_ko) for r in rows]


@router.get("/schema-comments/tables", response_model=list[SchemaCommentTableResponse])
def list_schema_comment_tables(table_name: str | None = None, db: Session = Depends(get_db)) -> list[SchemaCommentTableResponse]:
    rows = SchemaCommentService(db).list_tables(table_name=table_name)
    return [SchemaCommentTableResponse(**row) for row in rows]


@router.get("/schema-comments/tables/{table_name}/columns", response_model=list[SchemaCommentColumnResponse])
def list_schema_comment_columns(table_name: str, db: Session = Depends(get_db)) -> list[SchemaCommentColumnResponse]:
    rows = SchemaCommentService(db).list_columns(table_name=table_name)
    return [SchemaCommentColumnResponse(**row) for row in rows]
