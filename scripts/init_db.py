from __future__ import annotations

import sqlite3
from pathlib import Path


def ensure_markdown_content_column(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA table_info(research_reports);").fetchall()
    column_names = {row[1] for row in rows}
    if "markdown_content" not in column_names:
        conn.execute("ALTER TABLE research_reports ADD COLUMN markdown_content TEXT;")


def ensure_stock_master_columns(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA table_info(stocks);").fetchall()
    column_names = {row[1] for row in rows}
    add_columns: list[tuple[str, str]] = [
        ("isin_code", "TEXT"),
        ("corp_name", "TEXT"),
        ("corp_reg_no", "TEXT"),
        ("last_synced_at", "TEXT"),
        ("source", "TEXT"),
        ("security_type", "TEXT"),
    ]
    for column_name, column_type in add_columns:
        if column_name not in column_names:
            conn.execute(f"ALTER TABLE stocks ADD COLUMN {column_name} {column_type};")


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    db_dir = project_root / "db"
    db_dir.mkdir(parents=True, exist_ok=True)

    db_path = db_dir / "drct_asset.sqlite3"
    schema_path = project_root / "backend" / "app" / "sql" / "schema.sql"

    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    schema_sql = schema_path.read_text(encoding="utf-8")

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executescript(schema_sql)
        ensure_markdown_content_column(conn)
        ensure_stock_master_columns(conn)
        conn.commit()

    print(f"Database initialized at: {db_path}")


if __name__ == "__main__":
    main()
