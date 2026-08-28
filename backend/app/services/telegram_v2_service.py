from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.collectors.telegram.telegram_collector import TelegramCollector
from backend.app.core.config import now_kst
from backend.app.repositories.telegram_repository import TelegramRepository
from backend.app.services.telegram_article_service import TelegramArticleService
from backend.app.services.telegram_llm_service import TelegramLLMService
from backend.app.services.telegram_service import TelegramService as LegacyTelegramAuthService


class TelegramService(LegacyTelegramAuthService):
    """Inbox-oriented Telegram service. Provider text never crosses the persistence boundary."""

    URL_PATTERN = re.compile(r"https?://[^\s<>\]\[\"']+", re.IGNORECASE)
    TRACKING_KEYS = {"fbclid", "gclid", "igshid", "mc_cid", "mc_eid"}

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = TelegramRepository(db)
        self.collector = TelegramCollector()
        self.llm_service: TelegramLLMService | None = None
        self.article_service = TelegramArticleService()

    def delete_source(self, source_id: int) -> dict[str, bool]:
        source = self.repo.get_source(source_id)
        if not source:
            raise HTTPException(status_code=404, detail="telegram source not found")
        self.repo.delete_source_physical(source)
        return {"success": True}

    async def collect_source_by_date(self, source_id: int, target_date: str) -> dict[str, object]:
        source = self.repo.get_source(source_id)
        if not source or source.is_deleted == 1:
            raise HTTPException(status_code=404, detail="telegram source not found")
        self.repo.cleanup_exclusions(target_date)
        result = await self.collector.collect_channel_messages(
            source.source_name, source.channel_username, target_date
        )
        messages = list(result.get("messages") or []) if str(result.get("source_mode") or "") == "real" else []
        inserted = duplicate_skipped = excluded_skipped = processing_failed = 0
        last_message_id: int | None = None
        for message in messages:
            raw_text = str(message.get("message_text") or "").strip()
            source_url = self.extract_source_url(raw_text, str(message.get("message_url") or ""))
            fingerprint = self.build_fingerprint(raw_text, source_url)
            if not fingerprint:
                processing_failed += 1
                continue
            if self.repo.is_excluded(target_date, fingerprint):
                excluded_skipped += 1
                continue
            if self.repo.get_item_by_fingerprint(target_date, fingerprint):
                duplicate_skipped += 1
                continue
            title = self.derive_title(raw_text, source.source_name)
            if not title:
                processing_failed += 1
                continue
            try:
                self.repo.create_item({
                    "collection_date": target_date,
                    "message_at": str(message.get("message_date") or f"{target_date} 00:00:00"),
                    "title": title,
                    "summary": None,
                    "source_url": source_url,
                    "message_fingerprint": fingerprint,
                    "created_at": now_kst(),
                })
                inserted += 1
            except IntegrityError:
                self.db.rollback()
                duplicate_skipped += 1
            message_id = message.get("telegram_message_id")
            if isinstance(message_id, int):
                last_message_id = max(last_message_id or message_id, message_id)
        if result.get("success"):
            self.repo.update_source(source, {
                "last_collected_message_id": last_message_id or source.last_collected_message_id,
                "last_collected_at": now_kst(),
            })
        diagnostics = result.get("diagnostics") if isinstance(result.get("diagnostics"), dict) else {}
        return {
            "source_id": source.id,
            "source_name": source.source_name,
            "target_date": target_date,
            "source_mode": str(result.get("source_mode") or "not_connected"),
            "success": bool(result.get("success", False)),
            "telegram_connected": bool(result.get("telegram_connected", False)),
            "session_exists": bool(result.get("session_exists", False)),
            "channel_accessible": bool(result.get("channel_accessible", False)),
            "collected": len(messages),
            "inserted": inserted,
            "duplicate_skipped": duplicate_skipped,
            "excluded_skipped": excluded_skipped,
            "processing_failed": processing_failed,
            "error_code": result.get("error_code"),
            "error_message": result.get("message"),
            "diagnostics": diagnostics,
        }

    async def collect_all_sources_by_date(self, target_date: str) -> dict[str, object]:
        sources = self.repo.get_active_sources()
        totals = {key: 0 for key in (
            "collected", "inserted", "duplicate_skipped", "excluded_skipped", "processing_failed"
        )}
        results = [await self.collect_source_by_date(source.id, target_date) for source in sources]
        for result in results:
            for key in totals:
                totals[key] += int(result[key])
        errors = [str(row.get("error_message") or "") for row in results if not row.get("success")]
        return {
            "target_date": target_date,
            "source_count": len(sources),
            "source_mode": "real" if results and all(row.get("source_mode") == "real" for row in results) else "not_connected",
            "success": bool(results) and all(bool(row.get("success")) for row in results),
            "telegram_connected": bool(results) and all(bool(row.get("telegram_connected")) for row in results),
            "session_exists": bool(results) and all(bool(row.get("session_exists")) for row in results),
            "channel_accessible": bool(results) and all(bool(row.get("channel_accessible")) for row in results),
            **totals,
            "error_code": "PARTIAL_FAILURE" if errors else None,
            "error_message": "; ".join(errors) or None,
            "diagnostics": {},
        }

    def list_items(self, **filters: object) -> dict[str, object]:
        limit = int(filters.get("limit") or 20)
        offset = int(filters.get("offset") or 0)
        items, total, with_summary, title_only = self.repo.list_items(
            date_from=str(filters.get("date_from") or "") or None,
            date_to=str(filters.get("date_to") or "") or None,
            keyword=str(filters.get("keyword") or "").strip() or None,
            limit=limit, offset=offset,
        )
        return {"items": items, "total_count": total, "with_summary_count": with_summary,
                "title_only_count": title_only, "limit": limit, "offset": offset}

    def delete_item(self, item_id: int) -> dict[str, int]:
        if not self.repo.get_item(item_id):
            raise HTTPException(status_code=404, detail="telegram item not found")
        return {"requested_count": 1, "deleted_count": self.repo.delete_items_with_exclusion([item_id])}

    def delete_items(self, item_ids: list[int]) -> dict[str, int]:
        unique_ids = list(dict.fromkeys(int(value) for value in item_ids))
        return {"requested_count": len(unique_ids),
                "deleted_count": self.repo.delete_items_with_exclusion(unique_ids)}

    def summarize_items(self, item_ids: list[int]) -> dict[str, int]:
        unique_ids = list(dict.fromkeys(int(value) for value in item_ids))[:20]
        rows = self.repo.get_items(unique_ids)
        totals = {
            "requested": len(unique_ids), "summarized": 0, "skipped_existing": 0,
            "missing_url": 0, "fetch_failed": 0, "extraction_failed": 0, "processing_failed": 0,
        }
        fetch_failures = {
            "URL_FETCH_FAILED", "REDIRECT_LOCATION_MISSING", "TOO_MANY_REDIRECTS",
            "UNSUPPORTED_CONTENT_TYPE", "RESPONSE_TOO_LARGE", "SOURCE_INPUT_MISSING",
        }
        for item in rows:
            if item.summary:
                totals["skipped_existing"] += 1
                continue
            if not item.source_url:
                totals["missing_url"] += 1
                continue
            extraction = self.article_service.fetch_article(item.source_url, item.title)
            if not extraction.success:
                target = "fetch_failed" if extraction.failure_reason in fetch_failures else "extraction_failed"
                totals[target] += 1
                continue
            if self.llm_service is None:
                self.llm_service = TelegramLLMService()
            result = self.llm_service.summarize_article(extraction.text, item.title)
            if not result.get("success") or not result.get("summary"):
                totals["processing_failed"] += 1
                continue
            try:
                self.repo.update_summary(item, str(result["summary"]))
                totals["summarized"] += 1
            except Exception:
                self.db.rollback()
                totals["processing_failed"] += 1
        totals["processing_failed"] += max(0, len(unique_ids) - len(rows))
        return totals

    @classmethod
    def canonicalize_url(cls, value: str | None) -> str | None:
        raw = (value or "").strip().rstrip(".,;:!?)")
        if not raw:
            return None
        try:
            parts = urlsplit(raw)
            if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
                return None
            host = parts.netloc.lower()
            if host in {"t.me", "telegram.me", "www.t.me"}:
                return None
            query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                     if not k.lower().startswith("utm_") and k.lower() not in cls.TRACKING_KEYS]
            path = parts.path.rstrip("/") or "/"
            return urlunsplit((parts.scheme.lower(), host, path, urlencode(sorted(query)), ""))
        except Exception:
            return None

    @classmethod
    def extract_source_url(cls, raw_text: str, fallback_url: str | None = None) -> str | None:
        for candidate in cls.URL_PATTERN.findall(raw_text or "") + ([fallback_url] if fallback_url else []):
            canonical = cls.canonicalize_url(candidate)
            if canonical:
                return canonical
        return None

    @staticmethod
    def normalize_text(value: str) -> str:
        text = re.sub(r"https?://\S+", " ", value or "", flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", text).strip().lower()

    @classmethod
    def derive_title(cls, raw_text: str, source_name: str | None = None) -> str:
        """Build a usable title without starting the Local LLM during collection."""
        source_prefix = re.compile(
            rf"^\s*{re.escape(source_name)}\s*[-:|·]\s*" if source_name else r"a^",
            re.IGNORECASE,
        )
        for raw_line in (raw_text or "").splitlines():
            line = cls.URL_PATTERN.sub(" ", raw_line)
            line = re.sub(r"^[\s#>*•▪▫■□✅☑⚡🔥❤📌🚨📢🔲]+", "", line)
            line = source_prefix.sub("", line)
            line = re.sub(r"\s+", " ", line).strip(" -:|·\t")
            if len(re.sub(r"[^0-9A-Za-z가-힣]", "", line)) < 4:
                continue
            sentence = re.split(r"(?<=[.!?。])\s+", line, maxsplit=1)[0].strip()
            return (sentence or line)[:180]
        compact = re.sub(r"\s+", " ", cls.URL_PATTERN.sub(" ", raw_text or "")).strip()
        return compact[:180]

    @classmethod
    def build_fingerprint(cls, raw_text: str, source_url: str | None) -> str:
        canonical = cls.canonicalize_url(source_url)
        source = f"url:{canonical}" if canonical else f"text:{cls.normalize_text(raw_text)}"
        return hashlib.sha256(source.encode("utf-8")).hexdigest() if source not in {"text:", "url:"} else ""
