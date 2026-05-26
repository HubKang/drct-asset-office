from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timedelta
from html import unescape

from fastapi import HTTPException
import requests
from sqlalchemy.orm import Session

from backend.app.collectors.telegram.telegram_collector import TelegramCollector
from backend.app.core.config import now_kst
from backend.app.entities.telegram_source import TelegramSource
from backend.app.repositories.classification_rule_repository import ClassificationRuleRepository
from backend.app.repositories.collection_run_repository import CollectionRunRepository
from backend.app.repositories.telegram_repository import TelegramRepository
from backend.app.services.telegram_llm_service import TelegramLLMService


class TelegramService:
    _auth_sessions: dict[str, dict[str, object]] = {}
    URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)
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

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = TelegramRepository(db)
        self.collection_repo = CollectionRunRepository(db)
        self.classification_repo = ClassificationRuleRepository(db)
        self.collector = TelegramCollector()
        self.llm_service = TelegramLLMService()

    def list_sources(self, include_deleted: bool = False):
        return self.repo.list_sources(include_deleted=include_deleted)

    async def get_auth_status(self) -> dict[str, object]:
        status = await self.collector.get_connection_status(channel_username="")
        diagnostics = status.get("diagnostics") if isinstance(status.get("diagnostics"), dict) else {}
        source_mode = str(status.get("source_mode") or "not_connected")
        error_code = str(status.get("error_code") or "")
        error_message = str(status.get("message") or "")
        authorized = bool(source_mode == "real" and status.get("telegram_connected"))
        return {
            "enabled": bool(self.collector.enabled),
            "has_api_id": bool(diagnostics.get("has_api_id", False)),
            "has_api_hash": bool(diagnostics.get("has_api_hash", False)),
            "has_phone": bool(diagnostics.get("has_phone", False)),
            "has_session": bool(diagnostics.get("has_session", False)),
            "authorized": authorized,
            "auth_required": not authorized,
            "source_mode": source_mode,
            "error_code": error_code or ("TELEGRAM_AUTH_REQUIRED" if not authorized else None),
            "error_message": error_message or ("Telegram 인증이 필요합니다." if not authorized else None),
        }

    async def start_auth(self) -> dict[str, object]:
        if not self.collector.enabled:
            return {
                "success": False,
                "auth_stage": "failed",
                "authorized": False,
                "error_code": "TELEGRAM_NOT_CONFIGURED",
                "message": "Telegram 설정이 누락되어 인증을 시작할 수 없습니다.",
            }

        try:
            from telethon import TelegramClient  # type: ignore
        except Exception:
            return {
                "success": False,
                "auth_stage": "failed",
                "authorized": False,
                "error_code": "TELETHON_IMPORT_FAILED",
                "message": "Telethon 라이브러리 로드에 실패했습니다.",
            }

        from pathlib import Path
        from backend.app.core.config import TELEGRAM_API_HASH, TELEGRAM_API_ID, TELEGRAM_PHONE, TELEGRAM_SESSION_DIR

        session_dir = Path(TELEGRAM_SESSION_DIR)
        session_dir.mkdir(parents=True, exist_ok=True)
        session_path = session_dir / "drct_asset_telegram"

        client = TelegramClient(str(session_path), int(TELEGRAM_API_ID), TELEGRAM_API_HASH)
        try:
            await client.connect()
            if await client.is_user_authorized():
                return {
                    "success": True,
                    "auth_stage": "authorized",
                    "authorized": True,
                    "message": "이미 Telegram 인증이 완료된 상태입니다.",
                }

            sent = await client.send_code_request(TELEGRAM_PHONE)
            TelegramService._auth_sessions["default"] = {
                "phone_code_hash": str(getattr(sent, "phone_code_hash", "") or ""),
                "created_at": datetime.utcnow().isoformat(),
            }
            return {
                "success": True,
                "auth_stage": "code_required",
                "authorized": False,
                "message": "Telegram 앱으로 전송된 인증 코드를 입력해 주세요.",
            }
        except Exception as exc:
            return {
                "success": False,
                "auth_stage": "failed",
                "authorized": False,
                "error_code": "TELEGRAM_AUTH_START_FAILED",
                "message": f"인증 코드 요청에 실패했습니다: {exc}",
            }
        finally:
            await client.disconnect()

    async def verify_auth_code(self, code: str) -> dict[str, object]:
        safe_code = (code or "").strip()
        if not safe_code:
            raise HTTPException(status_code=400, detail="인증 코드를 입력해 주세요.")

        auth_session = TelegramService._auth_sessions.get("default") or {}
        phone_code_hash = str(auth_session.get("phone_code_hash") or "")
        created_at = str(auth_session.get("created_at") or "")
        if not phone_code_hash:
            return {
                "success": False,
                "auth_stage": "failed",
                "authorized": False,
                "error_code": "TELEGRAM_AUTH_SESSION_MISSING",
                "message": "인증 세션이 없습니다. 인증 시작을 다시 진행해 주세요.",
            }
        if created_at:
            try:
                created_dt = datetime.fromisoformat(created_at)
                if datetime.utcnow() - created_dt > timedelta(minutes=10):
                    TelegramService._auth_sessions.pop("default", None)
                    return {
                        "success": False,
                        "auth_stage": "failed",
                        "authorized": False,
                        "error_code": "TELEGRAM_AUTH_SESSION_EXPIRED",
                        "message": "인증 세션이 만료되었습니다. 인증 시작을 다시 진행해 주세요.",
                    }
            except Exception:
                pass

        try:
            from telethon import TelegramClient  # type: ignore
            from telethon.errors import SessionPasswordNeededError  # type: ignore
        except Exception:
            return {
                "success": False,
                "auth_stage": "failed",
                "authorized": False,
                "error_code": "TELETHON_IMPORT_FAILED",
                "message": "Telethon 라이브러리 로드에 실패했습니다.",
            }

        from pathlib import Path
        from backend.app.core.config import TELEGRAM_API_HASH, TELEGRAM_API_ID, TELEGRAM_PHONE, TELEGRAM_SESSION_DIR

        session_dir = Path(TELEGRAM_SESSION_DIR)
        session_dir.mkdir(parents=True, exist_ok=True)
        session_path = session_dir / "drct_asset_telegram"
        client = TelegramClient(str(session_path), int(TELEGRAM_API_ID), TELEGRAM_API_HASH)
        try:
            await client.connect()
            try:
                await client.sign_in(phone=TELEGRAM_PHONE, code=safe_code, phone_code_hash=phone_code_hash)
            except SessionPasswordNeededError:
                return {
                    "success": False,
                    "auth_stage": "password_required",
                    "authorized": False,
                    "error_code": "TELEGRAM_2FA_REQUIRED",
                    "message": "2단계 인증 비밀번호가 필요합니다.",
                }
            TelegramService._auth_sessions.pop("default", None)
            return {
                "success": True,
                "auth_stage": "authorized",
                "authorized": True,
                "message": "Telegram 인증이 완료되었습니다.",
            }
        except Exception as exc:
            return {
                "success": False,
                "auth_stage": "code_required",
                "authorized": False,
                "error_code": "TELEGRAM_AUTH_CODE_INVALID",
                "message": f"인증 코드 확인에 실패했습니다: {exc}",
            }
        finally:
            await client.disconnect()

    async def verify_auth_password(self, password: str) -> dict[str, object]:
        safe_password = (password or "").strip()
        if not safe_password:
            raise HTTPException(status_code=400, detail="2FA 비밀번호를 입력해 주세요.")

        try:
            from telethon import TelegramClient  # type: ignore
        except Exception:
            return {
                "success": False,
                "auth_stage": "failed",
                "authorized": False,
                "error_code": "TELETHON_IMPORT_FAILED",
                "message": "Telethon 라이브러리 로드에 실패했습니다.",
            }

        from pathlib import Path
        from backend.app.core.config import TELEGRAM_API_HASH, TELEGRAM_API_ID, TELEGRAM_SESSION_DIR

        session_dir = Path(TELEGRAM_SESSION_DIR)
        session_dir.mkdir(parents=True, exist_ok=True)
        session_path = session_dir / "drct_asset_telegram"
        client = TelegramClient(str(session_path), int(TELEGRAM_API_ID), TELEGRAM_API_HASH)
        try:
            await client.connect()
            await client.sign_in(password=safe_password)
            TelegramService._auth_sessions.pop("default", None)
            return {
                "success": True,
                "auth_stage": "authorized",
                "authorized": True,
                "message": "Telegram 인증이 완료되었습니다.",
            }
        except Exception as exc:
            return {
                "success": False,
                "auth_stage": "password_required",
                "authorized": False,
                "error_code": "TELEGRAM_AUTH_PASSWORD_INVALID",
                "message": f"2단계 인증 비밀번호 확인에 실패했습니다: {exc}",
            }
        finally:
            await client.disconnect()

    def create_source(self, payload) -> TelegramSource:
        now = now_kst()
        normalized_channel = self.collector.normalize_channel_username(payload.channel_username.strip())
        existing = self.repo.get_source_by_channel_username(normalized_channel)
        if existing:
            if existing.is_deleted == 1:
                return self.repo.update_source(
                    existing,
                    {
                        "source_name": payload.source_name.strip(),
                        "channel_title": (payload.channel_title or "").strip() or None,
                        "description": (payload.description or "").strip() or None,
                        "is_active": 1 if payload.is_active else 0,
                        "is_deleted": 0,
                        "memo": (payload.memo or "").strip() or None,
                        "updated_at": now,
                    },
                )
            raise HTTPException(status_code=409, detail="이미 등록된 채널입니다. username/link를 확인하세요.")

        source = TelegramSource(
            source_name=payload.source_name.strip(),
            channel_username=normalized_channel,
            channel_title=(payload.channel_title or "").strip() or None,
            source_type="channel",
            description=(payload.description or "").strip() or None,
            is_active=1 if payload.is_active else 0,
            is_default=0,
            is_deleted=0,
            last_collected_message_id=None,
            last_collected_at=None,
            memo=(payload.memo or "").strip() or None,
            created_at=now,
            updated_at=now,
        )
        return self.repo.create_source(source)

    def update_source(self, source_id: int, payload):
        source = self.repo.get_source(source_id)
        if not source:
            raise HTTPException(status_code=404, detail="telegram source not found")
        updates = payload.model_dump(exclude_unset=True)
        if "channel_username" in updates and isinstance(updates["channel_username"], str):
            updates["channel_username"] = self.collector.normalize_channel_username(updates["channel_username"])
        if "is_active" in updates:
            updates["is_active"] = 1 if updates["is_active"] else 0
        if "is_deleted" in updates:
            updates["is_deleted"] = 1 if updates["is_deleted"] else 0
        return self.repo.update_source(source, updates)

    def delete_source(self, source_id: int) -> dict[str, bool]:
        source = self.repo.get_source(source_id)
        if not source:
            raise HTTPException(status_code=404, detail="telegram source not found")
        item_count = self.repo.count_items_by_source(source_id)
        if item_count > 0:
            self.repo.update_source(source, {"is_active": 0, "is_deleted": 1})
            return {"success": True}
        self.repo.delete_source_physical(source)
        return {"success": True}

    async def test_source_connection(self, source_id: int) -> dict[str, object]:
        source = self.repo.get_source(source_id)
        if not source or source.is_deleted == 1:
            raise HTTPException(status_code=404, detail="telegram source not found")
        status = await self.collector.get_connection_status(source.channel_username)
        return {
            "source_id": source.id,
            "source_name": source.source_name,
            "channel_username": source.channel_username,
            "normalized_channel_username": status.get("normalized_channel_username"),
            "telegram_connected": bool(status.get("telegram_connected", False)),
            "session_exists": bool(status.get("session_exists", False)),
            "channel_accessible": bool(status.get("channel_accessible", False)),
            "source_mode": str(status.get("source_mode") or "not_connected"),
            "latest_message_id": status.get("latest_message_id"),
            "latest_message_date": status.get("latest_message_date"),
            "message": str(status.get("message") or ""),
        }

    async def collect_source_by_date(self, source_id: int, target_date: str, summarize_new_items: bool, include_notice: bool, include_advertisement: bool):
        source = self.repo.get_source(source_id)
        if not source or source.is_deleted == 1:
            raise HTTPException(status_code=404, detail="telegram source not found")

        run = self.collection_repo.create_running(
            collector_name=f"telegram_collect:{source.source_name}",
            target=f"{target_date}|{source.source_name}",
        )
        fetched = new_count = duplicate_count = summarized_count = failed_count = 0
        last_message_id: int | None = None
        try:
            collect_result = await self.collector.collect_channel_messages(source.source_name, source.channel_username, target_date)
            source_mode = str(collect_result.get("source_mode") or "not_connected")
            telegram_connected = bool(collect_result.get("telegram_connected", False))
            session_exists = bool(collect_result.get("session_exists", False))
            channel_accessible = bool(collect_result.get("channel_accessible", False))
            diagnostics = collect_result.get("diagnostics") if isinstance(collect_result.get("diagnostics"), dict) else {}
            error_code = str(collect_result.get("error_code") or "")
            error_message = str(collect_result.get("message") or "")
            messages = list(collect_result.get("messages") or [])
            if source_mode != "real":
                messages = []
            fetched = len(messages)
            rules = self.classification_repo.list_active_by_target("news")

            for msg in messages:
                telegram_message_id = int(msg["telegram_message_id"])
                existing = self.repo.get_item_by_source_message_id(source_id, telegram_message_id)
                if existing:
                    duplicate_count += 1
                    continue
                normalized_url = str(msg.get("message_url") or "").strip()
                if normalized_url:
                    existing_by_url = self.repo.get_item_by_source_normalized_url(source_id, normalized_url)
                    if existing_by_url:
                        duplicate_count += 1
                        continue

                item_title, normalized_text = self._resolve_item_title_and_text(
                    message_text=str(msg.get("message_text") or ""),
                    message_url=normalized_url,
                )

                item = self.repo.create_item(
                    {
                        "source_id": source_id,
                        "telegram_message_id": telegram_message_id,
                        "message_date": msg["message_date"],
                        "message_text": normalized_text,
                        "message_text_length": len(normalized_text),
                        "item_title": item_title or None,
                        "item_url": normalized_url or None,
                        "normalized_url": normalized_url or None,
                        "publisher": source.source_name,
                        "message_type": "unknown",
                        "item_category": "기타",
                        "summary_text": None,
                        "key_points_json": None,
                        "summary_error_message": None,
                        "tag": "기타",
                        "score": 50,
                        "sentiment": "neutral",
                        "risk_level": "unknown",
                        "event_type": "기타",
                        "related_stock_code": None,
                        "related_stock_name": None,
                        "related_theme": None,
                        "llm_model": None,
                        "summary_status": "pending",
                        "summary_has_content": 0,
                        "analysis_status": "pending",
                        "collected_at": now_kst(),
                        "summarized_at": None,
                        "created_at": now_kst(),
                        "updated_at": now_kst(),
                    }
                )
                new_count += 1
                last_message_id = max(last_message_id or 0, telegram_message_id)

                if summarize_new_items:
                    llm_input_text = self._build_llm_input_text(item.item_title, item.message_text)
                    summary_result = self.llm_service.summarize_and_classify(text=llm_input_text, rules=rules)
                    message_type = str(summary_result.get("message_type") or "unknown")
                    if not include_notice and message_type == "channel_notice":
                        continue
                    if not include_advertisement and message_type == "advertisement":
                        continue

                    has_content = int(summary_result.get("summary_has_content") or 0)
                    status = "summarized" if has_content == 1 else "failed"
                    if status == "summarized":
                        summarized_count += 1
                    else:
                        failed_count += 1

                    self.repo.update_item(
                        item,
                        {
                            "message_type": message_type,
                            "item_category": str(summary_result.get("item_category") or "기타"),
                            "summary_text": str(summary_result.get("summary_text") or "").strip() or None,
                            "key_points_json": json.dumps(summary_result.get("key_points") or [], ensure_ascii=False),
                            "tag": str(summary_result.get("tag") or "기타"),
                            "score": int(summary_result.get("score") or 50),
                            "sentiment": str(summary_result.get("sentiment") or "neutral"),
                            "risk_level": str(summary_result.get("risk_level") or "unknown"),
                            "event_type": str(summary_result.get("event_type") or "기타"),
                            "related_stock_name": str(summary_result.get("related_stock_name") or "") or None,
                            "related_stock_code": str(summary_result.get("related_stock_code") or "") or None,
                            "related_theme": str(summary_result.get("related_theme") or "") or None,
                            "summary_status": status,
                            "summary_has_content": has_content,
                            "summary_error_message": None if has_content == 1 else str(summary_result.get("summary_error_message") or "SUMMARY_INVALID"),
                            "analysis_status": status,
                            "summarized_at": now_kst(),
                            "llm_model": "lmstudio",
                        },
                    )

            self.repo.update_source(
                source,
                {
                    "last_collected_at": now_kst(),
                    "last_collected_message_id": last_message_id or source.last_collected_message_id,
                },
            )
            message = json.dumps(
                {
                    "target_date": target_date,
                    "source_name": source.source_name,
                    "fetched_message_count": fetched,
                    "new_item_count": new_count,
                    "duplicate_count": duplicate_count,
                    "summarized_count": summarized_count,
                    "failed_count": failed_count,
                },
                ensure_ascii=False,
            )
            if source_mode == "real":
                self.collection_repo.mark_success(run, message)
            else:
                self.collection_repo.mark_failed(run, f"{source_mode}:{error_code}:{error_message}")
        except Exception as exc:
            self.collection_repo.mark_failed(run, str(exc))
            raise

        return {
            "source_id": source.id,
            "source_name": source.source_name,
            "target_date": target_date,
            "source_mode": source_mode,
            "telegram_connected": telegram_connected,
            "session_exists": session_exists,
            "channel_accessible": channel_accessible,
            "success": source_mode == "real",
            "fetched_message_count": fetched,
            "new_item_count": new_count,
            "duplicate_count": duplicate_count,
            "summarized_count": summarized_count,
            "failed_count": failed_count,
            "error_code": error_code if source_mode != "real" else None,
            "error_message": error_message if source_mode != "real" else None,
            "diagnostics": diagnostics if source_mode != "real" else {},
            "collection_run_id": run.id,
        }

    async def collect_all_sources_by_date(self, target_date: str, summarize_new_items: bool, include_notice: bool, include_advertisement: bool):
        sources = self.repo.get_active_sources()
        result = {
            "target_date": target_date,
            "source_count": len(sources),
            "source_mode": "real",
            "telegram_connected": True,
            "session_exists": True,
            "channel_accessible": True,
            "success": True,
            "fetched_message_count": 0,
            "new_item_count": 0,
            "duplicate_count": 0,
            "summarized_count": 0,
            "failed_count": 0,
            "error_code": None,
            "error_message": None,
            "diagnostics": {},
        }
        for source in sources:
            each = await self.collect_source_by_date(
                source_id=source.id,
                target_date=target_date,
                summarize_new_items=summarize_new_items,
                include_notice=include_notice,
                include_advertisement=include_advertisement,
            )
            result["fetched_message_count"] += int(each["fetched_message_count"])
            result["new_item_count"] += int(each["new_item_count"])
            result["duplicate_count"] += int(each["duplicate_count"])
            result["summarized_count"] += int(each["summarized_count"])
            result["failed_count"] += int(each["failed_count"])
            if each.get("source_mode") != "real":
                result["source_mode"] = str(each.get("source_mode") or "not_connected")
                result["success"] = False
                result["error_code"] = each.get("error_code")
                result["error_message"] = each.get("error_message")
                if each.get("diagnostics"):
                    result["diagnostics"] = each.get("diagnostics")
            if each.get("telegram_connected") is False:
                result["telegram_connected"] = False
            if each.get("session_exists") is False:
                result["session_exists"] = False
            if each.get("channel_accessible") is False:
                result["channel_accessible"] = False
        return result

    def list_items(self, **filters):
        items, total_count = self.repo.list_items(**filters)
        deduped_items = []
        seen_keys: set[str] = set()
        for item in items:
            key = (item.normalized_url or "").strip().lower()
            if not key:
                key = re.sub(r"\s+", " ", (item.message_text or "").strip()).lower()
            if not key:
                key = f"id:{item.id}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            deduped_items.append(item)
        items = deduped_items
        source_map = self.repo.get_source_name_map([item.source_id for item in items])
        return {
            "items": [
                {
                    "id": item.id,
                    "source_id": item.source_id,
                    "source_name": source_map.get(item.source_id, "-"),
                    "telegram_message_id": item.telegram_message_id,
                    "message_date": item.message_date,
                    "message_text": item.message_text,
                    "item_title": item.item_title,
                    "summary_text": item.summary_text,
                    "key_points_json": item.key_points_json,
                    "message_type": item.message_type,
                    "item_category": item.item_category,
                    "tag": item.tag,
                    "score": item.score,
                    "sentiment": item.sentiment,
                    "risk_level": item.risk_level,
                    "event_type": item.event_type,
                    "related_stock_name": item.related_stock_name,
                    "related_stock_code": item.related_stock_code,
                    "related_theme": item.related_theme,
                    "summary_status": item.summary_status,
                    "summary_has_content": item.summary_has_content,
                    "summary_error_message": item.summary_error_message,
                    "item_url": item.item_url,
                    "normalized_url": item.normalized_url,
                    "updated_at": item.updated_at,
                }
                for item in items
            ],
            "total_count": total_count,
            "limit": int(filters.get("limit") or 50),
            "offset": int(filters.get("offset") or 0),
        }

    def summarize_item(self, item_id: int):
        item = self.repo.get_item(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="telegram item not found")
        rules = self.classification_repo.list_active_by_target("news")
        llm_input_text = self._build_llm_input_text(item.item_title, item.message_text)
        result = self.llm_service.summarize_and_classify(llm_input_text, rules=rules)
        has_content = int(result.get("summary_has_content") or 0)
        status = "summarized" if has_content == 1 else "failed"
        self.repo.update_item(
            item,
            {
                "message_type": str(result.get("message_type") or "unknown"),
                "item_category": str(result.get("item_category") or "기타"),
                "summary_text": str(result.get("summary_text") or "").strip() or None,
                "key_points_json": json.dumps(result.get("key_points") or [], ensure_ascii=False),
                "tag": str(result.get("tag") or "기타"),
                "score": int(result.get("score") or 50),
                "sentiment": str(result.get("sentiment") or "neutral"),
                "risk_level": str(result.get("risk_level") or "unknown"),
                "event_type": str(result.get("event_type") or "기타"),
                "related_stock_name": str(result.get("related_stock_name") or "") or None,
                "related_stock_code": str(result.get("related_stock_code") or "") or None,
                "related_theme": str(result.get("related_theme") or "") or None,
                "summary_status": status,
                "summary_has_content": has_content,
                "summary_error_message": None if has_content == 1 else str(result.get("summary_error_message") or "SUMMARY_INVALID"),
                "analysis_status": status,
                "summarized_at": now_kst(),
                "llm_model": "lmstudio",
            },
        )
        return {
            "item_id": item.id,
            "summary_status": status,
            "summary_has_content": has_content,
            "summary_text": item.summary_text,
            "summary_error_message": item.summary_error_message,
        }

    @classmethod
    def _strip_urls(cls, text: str) -> str:
        if not text:
            return ""
        return re.sub(r"\s+", " ", cls.URL_PATTERN.sub(" ", text)).strip()

    @classmethod
    def _extract_first_url(cls, text: str, fallback_url: str | None) -> str:
        found = cls.URL_PATTERN.search(text or "")
        if found:
            return found.group(0).strip()
        return (fallback_url or "").strip()

    def _resolve_item_title_and_text(self, message_text: str, message_url: str) -> tuple[str, str]:
        raw_text = (message_text or "").strip()
        cleaned_text = self._strip_urls(raw_text)
        if cleaned_text:
            return "", cleaned_text

        target_url = self._extract_first_url(raw_text, message_url)
        if not target_url:
            return "", raw_text

        title = self._fetch_title_from_url(target_url)
        if title:
            return title, ""
        return "", raw_text

    def _build_llm_input_text(self, item_title: str | None, message_text: str | None) -> str:
        title = (item_title or "").strip()
        body = (message_text or "").strip()
        if title and body:
            return f"{title}\n{body}"
        if title:
            return title
        return body

    @staticmethod
    def _fetch_title_from_url(url: str) -> str:
        try:
            response = requests.get(
                url,
                timeout=6,
                allow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (DrCTAssetBot/1.0)"},
            )
            response.raise_for_status()
            html_text = response.text or ""
            og_match = re.search(
                r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
                html_text,
                flags=re.IGNORECASE,
            )
            if og_match:
                normalized = TelegramService._normalize_title(unescape(og_match.group(1)))
                if TelegramService._is_valid_article_title(normalized):
                    return normalized

            twitter_match = re.search(
                r'<meta[^>]+name=["\']twitter:title["\'][^>]+content=["\']([^"\']+)["\']',
                html_text,
                flags=re.IGNORECASE,
            )
            if twitter_match:
                normalized = TelegramService._normalize_title(unescape(twitter_match.group(1)))
                if TelegramService._is_valid_article_title(normalized):
                    return normalized

            title_match = re.search(r"<title[^>]*>(.*?)</title>", html_text, flags=re.IGNORECASE | re.DOTALL)
            if title_match:
                normalized = TelegramService._normalize_title(unescape(re.sub(r"\s+", " ", title_match.group(1))))
                if TelegramService._is_valid_article_title(normalized):
                    return normalized
        except Exception:
            return ""
        return ""

    @staticmethod
    def _normalize_title(title: str) -> str:
        value = (title or "").strip()
        value = re.sub(r"\s+", " ", value)
        value = re.sub(r"\s*[\|\-:]\s*(네이버|NAVER|Naver|Telegram|t\.me).*$", "", value, flags=re.IGNORECASE)
        return value.strip()[:120]

    @classmethod
    def _is_valid_article_title(cls, title: str) -> bool:
        value = (title or "").strip()
        if len(value) < 6:
            return False
        normalized = re.sub(r"\s+", "", value).lower()
        return not any(pattern in normalized for pattern in cls.GENERIC_TITLE_PATTERNS)

    def delete_item(self, item_id: int) -> dict[str, int]:
        item = self.repo.get_item(item_id)
        if not item:
            raise HTTPException(status_code=404, detail="telegram item not found")
        self.repo.delete_item(item)
        return {"requested_count": 1, "deleted_count": 1}

    def delete_items(self, item_ids: list[int]) -> dict[str, int]:
        normalized_ids = sorted(set(int(x) for x in item_ids if int(x) > 0))
        if not normalized_ids:
            return {"requested_count": 0, "deleted_count": 0}
        deleted_count = self.repo.delete_items_by_ids(normalized_ids)
        return {"requested_count": len(normalized_ids), "deleted_count": deleted_count}

    def generate_daily_summary(self, target_date: str, source_id: int | None):
        sid = source_id if source_id is not None else 0
        data = self.repo.list_items(source_id=source_id, date_from=target_date, date_to=target_date, limit=5000, offset=0)
        items, _total = data
        tags = Counter((item.tag or "기타") for item in items)
        event_types = Counter((item.event_type or "기타") for item in items)
        msg_types = Counter((item.message_type or "unknown") for item in items)

        key_points = []
        for item in items[:8]:
            if item.summary_text:
                key_points.append(item.summary_text[:140])
        summary_text = "\n".join(f"- {line}" for line in key_points[:6]).strip()

        payload = {
            "summary_date": target_date,
            "source_id": sid,
            "item_count": len(items),
            "summary_text": summary_text or "요약 대상 메시지가 없습니다.",
            "key_points_json": json.dumps(key_points[:10], ensure_ascii=False),
            "theme_mentions_json": json.dumps([item.related_theme for item in items if item.related_theme][:10], ensure_ascii=False),
            "stock_mentions_json": json.dumps([item.related_stock_name for item in items if item.related_stock_name][:10], ensure_ascii=False),
            "risk_points_json": json.dumps([item.summary_text for item in items if item.risk_level in {"medium", "high"} and item.summary_text][:10], ensure_ascii=False),
            "top_tags_json": json.dumps([k for k, _ in tags.most_common(10)], ensure_ascii=False),
            "top_event_types_json": json.dumps([k for k, _ in event_types.most_common(10)], ensure_ascii=False),
            "message_type_stats_json": json.dumps([{"message_type": k, "count": v} for k, v in msg_types.most_common()], ensure_ascii=False),
            "market_view": None,
            "summary_has_content": 1 if summary_text else 0,
            "llm_model": "aggregate-rule",
            "elapsed_seconds": None,
            "created_at": now_kst(),
            "updated_at": now_kst(),
        }
        record = self.repo.upsert_daily_summary(payload)
        return {
            "id": record.id,
            "summary_date": record.summary_date,
            "source_id": record.source_id or 0,
            "item_count": record.item_count,
            "summary_text": record.summary_text,
            "key_points": self.repo.parse_json_array(record.key_points_json),
            "top_tags": self.repo.parse_json_array(record.top_tags_json),
            "top_event_types": self.repo.parse_json_array(record.top_event_types_json),
            "message_type_stats": json.loads(record.message_type_stats_json or "[]"),
            "theme_mentions": self.repo.parse_json_array(record.theme_mentions_json),
            "stock_mentions": self.repo.parse_json_array(record.stock_mentions_json),
            "risk_points": self.repo.parse_json_array(record.risk_points_json),
            "summary_has_content": record.summary_has_content,
            "llm_model": record.llm_model,
        }
