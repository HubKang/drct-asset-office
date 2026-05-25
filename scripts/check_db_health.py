from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.config import DATABASE_URL


def resolve_sqlite_path(database_url: str) -> Path:
    if not database_url.startswith("sqlite:///"):
        raise ValueError(f"sqlite only: {database_url}")

    parsed = urlparse(database_url)
    raw_path = unquote(parsed.path or "")
    if raw_path.startswith("/./"):
        raw_path = raw_path[1:]
    if raw_path.startswith("/") and len(raw_path) >= 3 and raw_path[2] == ":":
        raw_path = raw_path[1:]

    db_path = Path(raw_path)
    if not db_path.is_absolute():
        db_path = (PROJECT_ROOT / db_path).resolve()
    return db_path


def main() -> None:
    db_path = resolve_sqlite_path(DATABASE_URL)
    print(f"[DB_HEALTH] DATABASE_URL={DATABASE_URL}")
    print(f"[DB_HEALTH] sqlite_path={db_path}")
    print(f"[DB_HEALTH] exists={db_path.exists()}")
    print(f"[DB_HEALTH] size={db_path.stat().st_size if db_path.exists() else -1}")

    journal = Path(f"{db_path}-journal")
    wal = Path(f"{db_path}-wal")
    shm = Path(f"{db_path}-shm")
    print(f"[DB_HEALTH] journal_exists={journal.exists()}")
    print(f"[DB_HEALTH] wal_exists={wal.exists()}")
    print(f"[DB_HEALTH] shm_exists={shm.exists()}")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    print(f"[DB_HEALTH] integrity_check={cur.execute('PRAGMA integrity_check').fetchone()}")
    for table in ["stocks", "watchlist", "news_items", "disclosures", "collection_runs", "classification_rules", "telegram_sources", "telegram_items", "telegram_daily_summaries"]:
        try:
            count = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"[DB_HEALTH] {table}={count}")
        except Exception as exc:
            print(f"[DB_HEALTH] {table}=ERROR: {exc}")
    conn.close()

    print("[DB_HEALTH] git check guide:")
    print("  git status --short")
    print("  git ls-files | findstr sqlite")
    print("  git ls-files | findstr .env")


if __name__ == "__main__":
    main()
