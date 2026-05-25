from __future__ import annotations

import sqlite3
from pathlib import Path


def main() -> None:
    db_path = Path(__file__).resolve().parents[1] / "db" / "drct_asset.sqlite3"
    if not db_path.exists():
        raise SystemExit(f"[MIGRATE] DB not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()

        table = cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='stock_daily_market_metrics'"
        ).fetchone()
        if not table:
            raise SystemExit("[MIGRATE] table not found: stock_daily_market_metrics")

        cols = cur.execute("PRAGMA table_info(stock_daily_market_metrics)").fetchall()
        col_names = {row[1] for row in cols}
        if "foreign_ownership_ratio" in col_names:
            print("[MIGRATE] column already exists: foreign_ownership_ratio")
        else:
            cur.execute("ALTER TABLE stock_daily_market_metrics ADD COLUMN foreign_ownership_ratio REAL")
            conn.commit()
            print("[MIGRATE] added column: foreign_ownership_ratio REAL")

        cols_after = cur.execute("PRAGMA table_info(stock_daily_market_metrics)").fetchall()
        for row in cols_after:
            print(row)
    finally:
        conn.close()


if __name__ == "__main__":
    main()

