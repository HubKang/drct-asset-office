from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from backend.app.core.config import (
    TELEGRAM_API_HASH,
    TELEGRAM_API_ID,
    TELEGRAM_COLLECT_MAX_MESSAGES_PER_DAY,
    TELEGRAM_ENABLED,
    TELEGRAM_PHONE,
    TELEGRAM_SESSION_DIR,
    TELEGRAM_USE_MOCK,
)


class TelegramCollector:
    def __init__(self) -> None:
        self.enabled = TELEGRAM_ENABLED and bool(TELEGRAM_API_ID and TELEGRAM_API_HASH and TELEGRAM_PHONE)

    @staticmethod
    def _resolve_date_range(target_date: str) -> tuple[datetime, datetime]:
        start = datetime.strptime(target_date, "%Y-%m-%d").replace(tzinfo=ZoneInfo("Asia/Seoul"))
        end = start + timedelta(days=1)
        return start, end

    @staticmethod
    def normalize_channel_username(channel_username: str) -> str:
        value = (channel_username or "").strip()
        if not value:
            return value
        lower = value.lower()
        if lower.startswith("https://t.me/"):
            value = value[13:]
        elif lower.startswith("http://t.me/"):
            value = value[12:]
        elif lower.startswith("t.me/"):
            value = value[5:]
        value = value.split("/")[0].strip()
        if not value:
            return value
        if value.startswith("@"):
            value = value[1:].strip()
        return value

    def _session_exists(self) -> bool:
        session_dir = Path(TELEGRAM_SESSION_DIR)
        session_path = session_dir / "drct_asset_telegram"
        return bool(session_path.exists() or session_path.with_suffix(".session").exists())

    async def get_connection_status(self, channel_username: str) -> dict[str, object]:
        normalized_channel = self.normalize_channel_username(channel_username)
        has_api_id = bool(str(TELEGRAM_API_ID or "").strip())
        has_api_hash = bool(str(TELEGRAM_API_HASH or "").strip())
        has_phone = bool(str(TELEGRAM_PHONE or "").strip())
        session_exists = self._session_exists()
        status: dict[str, object] = {
            "source_mode": "not_connected",
            "telegram_connected": False,
            "session_exists": session_exists,
            "channel_accessible": False,
            "normalized_channel_username": normalized_channel,
            "latest_message_id": None,
            "latest_message_date": None,
            "message": "",
            "error_code": None,
            "diagnostics": {
                "has_api_id": has_api_id,
                "has_api_hash": has_api_hash,
                "has_phone": has_phone,
                "has_session": session_exists,
                "channel_resolved": False,
                "telethon_import_ok": False,
            },
        }

        if not self.enabled:
            status["message"] = "Telegram 환경변수 미설정 또는 TELEGRAM_ENABLED=false"
            status["error_code"] = "TELEGRAM_NOT_CONFIGURED"
            return status

        try:
            from telethon import TelegramClient  # type: ignore
            status["diagnostics"]["telethon_import_ok"] = True  # type: ignore[index]
        except Exception as exc:
            status["message"] = f"telethon import 실패: {exc}"
            status["error_code"] = "TELETHON_IMPORT_FAILED"
            return status

        session_dir = Path(TELEGRAM_SESSION_DIR)
        session_dir.mkdir(parents=True, exist_ok=True)
        session_path = session_dir / "drct_asset_telegram"

        client = TelegramClient(str(session_path), int(TELEGRAM_API_ID), TELEGRAM_API_HASH)
        try:
            await client.connect()
            if not await client.is_user_authorized():
                status["message"] = "Telegram 세션 파일은 존재하지만 사용자 인증이 완료되지 않았습니다."
                status["error_code"] = "TELEGRAM_AUTH_REQUIRED"
                return status

            status["telegram_connected"] = True
            status["source_mode"] = "real"

            try:
                entity = await client.get_entity(normalized_channel or channel_username)
                if getattr(entity, "broadcast", None) is not True:
                    status["message"] = "채널 접근 실패: channel 타입만 허용됩니다."
                    status["error_code"] = "TELEGRAM_CHANNEL_TYPE_INVALID"
                    return status

                status["channel_accessible"] = True
                status["diagnostics"]["channel_resolved"] = True  # type: ignore[index]
                latest = await client.get_messages(entity, limit=1)
                if latest and len(latest) > 0:
                    msg = latest[0]
                    status["latest_message_id"] = int(getattr(msg, "id", 0) or 0) or None
                    msg_dt = getattr(msg, "date", None)
                    if msg_dt:
                        status["latest_message_date"] = msg_dt.astimezone(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S")
                status["message"] = "채널 접근 테스트에 성공했습니다."
            except Exception as exc:
                status["message"] = f"채널 접근 테스트 실패: {exc}"
                status["error_code"] = "TELEGRAM_CHANNEL_RESOLVE_FAILED"
        except Exception as exc:
            status["source_mode"] = "not_connected"
            status["message"] = f"텔레그램 연결 실패: {exc}"
            status["error_code"] = "TELEGRAM_CONNECT_FAILED"
        finally:
            await client.disconnect()

        return status

    async def collect_channel_messages(self, source_name: str, channel_username: str, target_date: str) -> dict[str, object]:
        normalized_channel = self.normalize_channel_username(channel_username)
        base_status = await self.get_connection_status(channel_username=normalized_channel)

        if base_status.get("source_mode") != "real":
            if TELEGRAM_USE_MOCK:
                return {
                    **base_status,
                    "source_mode": "mock",
                    "message": "Telegram 연결 실패로 mock 모드 데이터(비저장)만 반환합니다.",
                    "messages": self._collect_mock_messages(
                        source_name=source_name,
                        channel_username=normalized_channel or channel_username,
                        target_date=target_date,
                    ),
                }
            return {
                **base_status,
                "messages": [],
            }

        try:
            from telethon import TelegramClient  # type: ignore
        except Exception as exc:
            return {
                **base_status,
                "source_mode": "error",
                "message": f"telethon import 실패: {exc}",
                "error_code": "TELETHON_IMPORT_FAILED",
                "messages": [],
            }

        session_dir = Path(TELEGRAM_SESSION_DIR)
        session_dir.mkdir(parents=True, exist_ok=True)
        session_path = session_dir / "drct_asset_telegram"
        start, end = self._resolve_date_range(target_date)

        client = TelegramClient(str(session_path), int(TELEGRAM_API_ID), TELEGRAM_API_HASH)
        try:
            await client.connect()
            entity = await client.get_entity(normalized_channel or channel_username)
            if getattr(entity, "broadcast", None) is not True:
                return {
                    **base_status,
                    "source_mode": "error",
                    "channel_accessible": False,
                    "message": "채널 접근 실패: channel 타입만 허용됩니다.",
                    "error_code": "TELEGRAM_CHANNEL_TYPE_INVALID",
                    "messages": [],
                }

            messages: list[dict] = []
            async for msg in client.iter_messages(entity, limit=TELEGRAM_COLLECT_MAX_MESSAGES_PER_DAY):
                if not getattr(msg, "id", None) or not getattr(msg, "date", None):
                    continue
                msg_dt_kst = msg.date.astimezone(ZoneInfo("Asia/Seoul"))
                if msg_dt_kst < start:
                    break
                if msg_dt_kst >= end:
                    continue
                text = (getattr(msg, "message", None) or "").strip()
                article_url = self._extract_first_external_url(text)
                messages.append(
                    {
                        "telegram_message_id": int(msg.id),
                        "message_date": msg_dt_kst.strftime("%Y-%m-%d %H:%M:%S"),
                        "message_text": text,
                        "message_url": article_url or self._build_message_url(normalized_channel or channel_username, int(msg.id)),
                    }
                )

            return {
                **base_status,
                "source_mode": "real",
                "telegram_connected": True,
                "channel_accessible": True,
                "normalized_channel_username": normalized_channel or channel_username,
                "messages": messages,
            }
        except Exception as exc:
            return {
                **base_status,
                "source_mode": "error",
                "channel_accessible": False,
                "message": f"텔레그램 수집 실패: {exc}",
                "error_code": "TELEGRAM_COLLECT_FAILED",
                "messages": [],
            }
        finally:
            await client.disconnect()

    @staticmethod
    def _build_message_url(channel_username: str, message_id: int) -> str:
        username = channel_username.strip().lstrip("@").replace("https://t.me/", "").replace("http://t.me/", "").replace("t.me/", "")
        username = username.split("/")[0]
        if not username:
            return ""
        return f"https://t.me/{username}/{message_id}"

    @staticmethod
    def _extract_first_external_url(text: str) -> str:
        if not text:
            return ""
        matches = re.findall(r"https?://\S+", text, flags=re.IGNORECASE)
        for raw in matches:
            candidate = raw.strip().rstrip(").,]")
            lowered = candidate.lower()
            if "t.me/" in lowered or "telegram.me/" in lowered:
                continue
            return candidate
        return ""

    def _collect_mock_messages(self, source_name: str, channel_username: str, target_date: str) -> list[dict]:
        seed = abs(hash(f"{source_name}|{channel_username}|{target_date}")) % 10000
        base_id = seed * 10
        samples = [
            f"[{source_name}] AI 반도체 수급 이슈 및 대형주 실적 기대감 요약 ({target_date})",
            f"[{source_name}] 정책/금리 변수로 변동성 확대 가능성 점검 필요 ({target_date})",
            f"[{source_name}] 특정 종목 급등 언급, 근거 확인 필요 및 리스크 경고 ({target_date})",
        ]
        return [
            {
                "telegram_message_id": base_id + idx + 1,
                "message_date": f"{target_date} 09:0{idx}:00",
                "message_text": text,
                "message_url": self._build_message_url(channel_username, base_id + idx + 1),
            }
            for idx, text in enumerate(samples)
        ]
