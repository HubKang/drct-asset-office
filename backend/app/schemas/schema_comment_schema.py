from __future__ import annotations

from pydantic import BaseModel


class SchemaCommentResponse(BaseModel):
    table_name: str
    column_name: str | None
    comment_ko: str


class SchemaCommentTableResponse(BaseModel):
    table_id: str
    table_name: str
    table_comment_ko: str | None
    column_count: int


class SchemaCommentColumnResponse(BaseModel):
    column_id: int
    column_name: str
    is_pk: bool
    is_nullable: bool
    data_type: str
    data_length: int | None
    default_value: str | None
    comment_ko: str | None
