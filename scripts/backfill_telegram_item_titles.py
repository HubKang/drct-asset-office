from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime
from html import unescape
from pathlib import Path
from typing import Any

import requests

from backend.app.core.database import SessionLocal
from backend.app.core.config import now_kst
from backend.app.entities.telegram_item import TelegramItem


URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)
OG_TITLE_PATTERN = re.compile(
    r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
    flags=re.IGNORECASE,
)
TITLE_PATTERN = re.compile(r"<title[^>]*>(.*?)</title>", flags=re.IGNORECASE | re.DOTALL)
GENERIC_TITLE_PATTERNS = [
    "telegram",
    "t.me",
    "naver",
    "네이버",
    "네이버뉴스",
    "telegram:contact",
    "채널보기",
    "주식급등일보",
    "급등테마",
    "대장주탐색기",
    "koreanstocks",
    "번개맞은뉴스",
    "faststocknews",
]


@dataclass
class BackfillResult:
    id: int
    url: str
    status: str
    reason: str
    extracted_title: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill item_title for URL-only telegram_items rows.")
    parser.add_argument("--apply", action="store_true", help="Apply DB updates. Default is dry-run.")
    parser.add_argument("--limit", type=int, default=0, help="Process at most N rows (0 means all).")
    return parser.parse_args()


def pick_target_url(item: TelegramItem) -> str:
    text = (item.message_text or "").strip()
    m = URL_PATTERN.search(text)
    if m:
        return m.group(0).strip().rstrip(").,]")
    normalized = (item.normalized_url or "").strip()
    if normalized:
        return normalized
    url = (item.item_url or "").strip()
    if url:
        return url
    return ""


def fetch_title(url: str) -> tuple[str, str]:
    try:
        response = requests.get(
            url,
            timeout=6,
            allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (DrCTAssetBot/1.0)"},
        )
        response.raise_for_status()
        html = response.text or ""

        og_match = OG_TITLE_PATTERN.search(html)
        if og_match:
            title = normalize_title(unescape(og_match.group(1)))
            if is_valid_title(title):
                return title, "ok:og_title"

        tw_match = re.search(
            r'<meta[^>]+name=["\']twitter:title["\'][^>]+content=["\']([^"\']+)["\']',
            html,
            flags=re.IGNORECASE,
        )
        if tw_match:
            title = normalize_title(unescape(tw_match.group(1)))
            if is_valid_title(title):
                return title, "ok:twitter_title"

        title_match = TITLE_PATTERN.search(html)
        if title_match:
            title = normalize_title(unescape(re.sub(r"\s+", " ", title_match.group(1))))
            if is_valid_title(title):
                return title, "ok:title_tag"

        return "", "GENERIC_OR_NO_TITLE"
    except requests.exceptions.Timeout:
        return "", "REQUEST_TIMEOUT"
    except requests.exceptions.HTTPError as exc:
        return "", f"HTTP_ERROR:{exc.response.status_code if exc.response else 'unknown'}"
    except requests.exceptions.RequestException as exc:
        return "", f"REQUEST_ERROR:{type(exc).__name__}"
    except Exception as exc:  # noqa: BLE001
        return "", f"UNKNOWN_ERROR:{type(exc).__name__}"


def normalize_title(title: str) -> str:
    value = (title or "").strip()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"\s*[\|\-:]\s*(네이버|NAVER|Naver|Telegram|t\.me).*$", "", value, flags=re.IGNORECASE)
    return value.strip()[:120]


def is_valid_title(title: str) -> bool:
    if not title or len(title.strip()) < 6:
        return False
    normalized = title.replace(" ", "").lower()
    return not any(pattern in normalized for pattern in GENERIC_TITLE_PATTERNS)


def make_report(results: list[BackfillResult], apply: bool) -> Path:
    project_root = Path(__file__).resolve().parents[1]
    reports_dir = project_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = reports_dir / f"backfill_telegram_item_titles_{'apply' if apply else 'dryrun'}_{ts}.json"
    payload: dict[str, Any] = {
        "mode": "apply" if apply else "dry-run",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "target_count": len(results),
        "success_count": sum(1 for r in results if r.status == "success"),
        "failed_count": sum(1 for r in results if r.status == "failed"),
        "results": [
            {
                "id": r.id,
                "url": r.url,
                "status": r.status,
                "reason": r.reason,
                "extracted_title": r.extracted_title,
            }
            for r in results
        ],
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path


def main() -> None:
    args = parse_args()
    db = SessionLocal()
    try:
        query = (
            db.query(TelegramItem)
            .filter(
                (
                    (TelegramItem.item_title.is_(None))
                    | (TelegramItem.item_title == "")
                    | (TelegramItem.item_title.like("%Telegram%"))
                    | (TelegramItem.item_title.like("%NAVER%"))
                    | (TelegramItem.item_title.like("%네이버%"))
                    | (TelegramItem.item_title.like("%주식급등일보%"))
                    | (TelegramItem.item_title.like("%번개맞은뉴스%"))
                    | (TelegramItem.item_title.like("%FastStockNews%"))
                ),
                ((TelegramItem.item_url.is_not(None)) | (TelegramItem.normalized_url.is_not(None)))
                | (TelegramItem.message_text.like("http%"))
                | (TelegramItem.message_text.like("%naver.me%")),
            )
            .order_by(TelegramItem.id.desc())
        )
        if args.limit and args.limit > 0:
            query = query.limit(args.limit)
        rows = list(query.all())

        results: list[BackfillResult] = []
        success_count = 0
        failed_count = 0

        for item in rows:
            url = pick_target_url(item)
            if not url:
                failed_count += 1
                results.append(BackfillResult(id=item.id, url="", status="failed", reason="NO_URL"))
                continue

            title, reason = fetch_title(url)
            if not title:
                failed_count += 1
                results.append(BackfillResult(id=item.id, url=url, status="failed", reason=reason))
                continue

            success_count += 1
            results.append(
                BackfillResult(
                    id=item.id,
                    url=url,
                    status="success",
                    reason=reason,
                    extracted_title=title,
                )
            )
            if args.apply:
                item.item_title = title
                item.updated_at = now_kst()
                db.add(item)

        if args.apply:
            db.commit()
        else:
            db.rollback()

        report_path = make_report(results, apply=args.apply)
        print(f"[TITLE BACKFILL] mode={'apply' if args.apply else 'dry-run'}")
        print(f"[TITLE BACKFILL] target_count={len(rows)}")
        print(f"[TITLE BACKFILL] success_count={success_count}")
        print(f"[TITLE BACKFILL] failed_count={failed_count}")
        print(f"[TITLE BACKFILL] report={report_path}")

        failure_reason_count: dict[str, int] = {}
        for r in results:
            if r.status != "failed":
                continue
            failure_reason_count[r.reason] = failure_reason_count.get(r.reason, 0) + 1
        if failure_reason_count:
            print("[TITLE BACKFILL] failure_reasons:")
            for reason, count in sorted(failure_reason_count.items(), key=lambda x: x[0]):
                print(f"  - {reason}: {count}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
