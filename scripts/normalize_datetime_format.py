from __future__ import annotations

import re
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "db" / "drct_asset.sqlite3"
TARGET_COLUMNS: dict[str, list[str]] = {
    "stocks": ["created_at", "updated_at"],
    "watchlist": ["registered_at", "updated_at"],
    "news_items": ["published_at", "collected_at", "created_at"],
    "disclosures": ["disclosed_at", "created_at"],
    "price_daily": ["created_at"],
    "research_reports": ["created_at"],
    "gpt_advisories": ["created_at"],
    "investment_decisions": ["created_at"],
    "risk_reviews": ["created_at"],
    "trade_reviews": ["created_at"],
    "collection_runs": ["started_at", "finished_at", "created_at"],
    "schema_comments": ["created_at"],
}

STD_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")


def to_std_datetime(value: str) -> str | None:
    if STD_PATTERN.match(value):
        return None

    candidate = value.strip().replace("Z", "+00:00")

    try:
        dt = datetime.fromisoformat(candidate)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass

    for fmt in (
        "%a, %d %b %Y %H:%M:%S %z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
    ):
        try:
            dt = datetime.strptime(candidate, fmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            continue

    return None


def main() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database file not found: {DB_PATH}")

    total_updated = 0
    total_warn = 0

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        for table, columns in TARGET_COLUMNS.items():
            rows = cur.execute(f"SELECT rowid AS _rowid_, * FROM {table}").fetchall()
            for row in rows:
                rowid = row["_rowid_"]
                for col in columns:
                    current = row[col]
                    if current is None:
                        continue
                    normalized = to_std_datetime(str(current))
                    if normalized is None:
                        if STD_PATTERN.match(str(current)):
                            continue
                        total_warn += 1
                        print(f"[WARN] skip unparseable {table}.{col} rowid={rowid}: {current}")
                        continue
                    if normalized != current:
                        cur.execute(f"UPDATE {table} SET {col} = ? WHERE rowid = ?", (normalized, rowid))
                        total_updated += 1

        conn.commit()

    print(f"Normalized datetime values: {total_updated}")
    print(f"Warnings (unparseable): {total_warn}")


if __name__ == "__main__":
    main()
