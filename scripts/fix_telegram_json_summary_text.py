from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

DB_PATH = Path("db/drct_asset.sqlite3")


def looks_like_json_object(text: str) -> bool:
    s = (text or "").strip()
    return s.startswith("{")


def normalize_row(summary_text: str, key_points_json: str | None):
    summary_text = (summary_text or "").strip()
    if not looks_like_json_object(summary_text):
        return None
    try:
        outer = json.loads(summary_text)
        if not isinstance(outer, dict):
            return None
    except Exception:
        # Try to salvage first JSON object block
        start = summary_text.find("{")
        end = summary_text.rfind("}")
        if start >= 0 and end > start:
            try:
                outer = json.loads(summary_text[start : end + 1])
                if not isinstance(outer, dict):
                    return None
            except Exception:
                return "parse_failed"
        else:
            return "parse_failed"

    summary = str(outer.get("summary_text") or outer.get("summary") or "").strip()
    points = outer.get("key_points") or outer.get("points") or []
    if isinstance(points, str):
        points = [points]
    if not isinstance(points, list):
        points = []
    points = [str(v).strip() for v in points if str(v).strip()]

    fields = {
        "message_type": outer.get("message_type"),
        "item_category": outer.get("item_category"),
        "tag": outer.get("tag"),
        "score": outer.get("score"),
        "sentiment": outer.get("sentiment"),
        "risk_level": outer.get("risk_level"),
        "event_type": outer.get("event_type"),
    }

    if not summary:
        return {
            "summary_status": "failed",
            "summary_has_content": 0,
            "summary_text": None,
            "key_points_json": "[]",
            **{k: v for k, v in fields.items() if v not in (None, "")},
        }

    return {
        "summary_status": "summarized",
        "summary_has_content": 1,
        "summary_text": summary,
        "key_points_json": json.dumps(points, ensure_ascii=False),
        **{k: v for k, v in fields.items() if v not in (None, "")},
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="apply updates")
    args = parser.parse_args()

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    rows = cur.execute(
        """
        SELECT id, summary_text, key_points_json
        FROM telegram_items
        WHERE trim(ifnull(summary_text,'')) LIKE '{%'
        """
    ).fetchall()

    total = len(rows)
    updated = 0
    failed_parse = 0

    print(f"[fix_telegram_json_summary_text] target_rows={total} apply={args.apply}")

    for row_id, summary_text, key_points_json in rows:
        normalized = normalize_row(summary_text or "", key_points_json)
        if normalized == "parse_failed":
            failed_parse += 1
            if args.apply:
                cur.execute(
                    "UPDATE telegram_items SET summary_status='failed', summary_has_content=0, summary_text=NULL, key_points_json='[]' WHERE id=?",
                    (row_id,),
                )
                updated += 1
            print(f"- id={row_id} parse_failed")
            continue
        if not normalized:
            continue

        print(f"- id={row_id} -> status={normalized['summary_status']} summary_len={len((normalized.get('summary_text') or ''))}")
        if args.apply:
            set_parts = []
            values = []
            for k, v in normalized.items():
                set_parts.append(f"{k}=?")
                values.append(v)
            values.append(row_id)
            cur.execute(f"UPDATE telegram_items SET {', '.join(set_parts)} WHERE id=?", values)
            updated += 1

    if args.apply:
        con.commit()

    print(f"[fix_telegram_json_summary_text] updated={updated} failed_parse={failed_parse}")
    con.close()


if __name__ == "__main__":
    main()
