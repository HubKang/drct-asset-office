from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.utils.stock_code import normalize_stock_code


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    db_path = Path("db/drct_asset.sqlite3")
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    rows = cur.execute(
        """
        SELECT id, stock_code, stock_code_raw, stock_name
        FROM kiwoom_condition_result_items
        WHERE instr(stock_code, '_') > 0
           OR LENGTH(stock_code) <> 6
        ORDER BY id DESC
        """
    ).fetchall()

    recoverable: list[tuple[int, str]] = []
    unrecoverable: list[sqlite3.Row] = []

    for row in rows:
        fixed = normalize_stock_code(row["stock_code_raw"]) or normalize_stock_code(row["stock_code"])
        if len(fixed) == 6:
            recoverable.append((int(row["id"]), fixed))
        else:
            unrecoverable.append(row)

    print(
        {
            "mode": "apply" if args.apply else "dry-run",
            "target_count": len(rows),
            "recoverable_count": len(recoverable),
            "unrecoverable_count": len(unrecoverable),
        }
    )

    if recoverable:
        print("recoverable_sample:", recoverable[:10])
    if unrecoverable:
        sample = [
            {
                "id": int(r["id"]),
                "stock_code": r["stock_code"],
                "stock_code_raw": r["stock_code_raw"],
                "stock_name": r["stock_name"],
            }
            for r in unrecoverable[:10]
        ]
        print("unrecoverable_sample:", sample)

    if args.apply and recoverable:
        cur.executemany("UPDATE kiwoom_condition_result_items SET stock_code=? WHERE id=?", [(code, rid) for rid, code in recoverable])
        con.commit()
        print({"updated_count": len(recoverable)})
    else:
        print({"updated_count": 0})

    con.close()


if __name__ == "__main__":
    main()
