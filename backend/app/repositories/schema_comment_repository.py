from __future__ import annotations

import re

from sqlalchemy import Select, select, text
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

    def list_tables(self, table_name: str | None) -> list[dict[str, object]]:
        comments = self.list(table_name=table_name)
        table_comments: dict[str, str] = {}
        column_counts: dict[str, int] = {}

        for row in comments:
            if row.column_name is None:
                table_comments[row.table_name] = row.comment_ko
                column_counts.setdefault(row.table_name, 0)
                continue
            column_counts[row.table_name] = column_counts.get(row.table_name, 0) + 1
            table_comments.setdefault(row.table_name, None)

        table_rows: list[dict[str, object]] = []
        for name in sorted(table_comments.keys()):
            table_rows.append(
                {
                    "table_id": name,
                    "table_name": table_comments.get(name) or name,
                    "table_comment_ko": table_comments.get(name),
                    "column_count": column_counts.get(name, 0),
                }
            )
        return table_rows

    def list_columns(self, table_name: str) -> list[dict[str, object]]:
        comment_rows = self.list(table_name=table_name)
        comment_map: dict[str, str] = {
            r.column_name: r.comment_ko for r in comment_rows if r.column_name is not None
        }

        escaped_table_name = table_name.replace('"', '""')
        pragma_rows = self.db.execute(text(f'PRAGMA table_info("{escaped_table_name}")')).mappings().all()
        columns: list[dict[str, object]] = []
        for row in pragma_rows:
            dtype = str(row.get("type") or "").strip()
            data_length: int | None = None
            match = re.search(r"\((\d+)\)", dtype)
            if match:
                try:
                    data_length = int(match.group(1))
                except ValueError:
                    data_length = None
            columns.append(
                {
                    "column_id": int(row.get("cid") or 0),
                    "column_name": str(row.get("name") or ""),
                    "is_pk": int(row.get("pk") or 0) > 0,
                    "is_nullable": int(row.get("notnull") or 0) == 0,
                    "data_type": dtype or "-",
                    "data_length": data_length,
                    "default_value": None if row.get("dflt_value") is None else str(row.get("dflt_value")),
                    "comment_ko": comment_map.get(str(row.get("name") or "")),
                }
            )
        return columns
