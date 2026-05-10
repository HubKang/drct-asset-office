from __future__ import annotations

from pydantic import BaseModel


class SchemaCommentResponse(BaseModel):
    table_name: str
    column_name: str | None
    comment_ko: str
