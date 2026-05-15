from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

from backend.app.core.config import (
    KIS_ACCESS_TOKEN,
    KIS_APP_KEY,
    KIS_APP_SECRET,
    KIS_BASE_URL,
    KIS_PAPER_BASE_URL,
    KIS_TIMEOUT_SECONDS,
    KIS_TOKEN_EXPIRES_AT,
    KIS_USE_PAPER,
    PROJECT_ROOT,
)

logger = logging.getLogger(__name__)


class KisAuthClient:
    def __init__(self) -> None:
        self.app_key = KIS_APP_KEY
        self.app_secret = KIS_APP_SECRET
        self.timeout = KIS_TIMEOUT_SECONDS
        self.base_url = KIS_PAPER_BASE_URL if KIS_USE_PAPER else KIS_BASE_URL
        self._token: str | None = KIS_ACCESS_TOKEN or None
        self._token_expires_at: datetime | None = self._parse_expires(KIS_TOKEN_EXPIRES_AT)
        self._cache_path = PROJECT_ROOT / ".kis_token.json"
        self._load_token_cache()

    @staticmethod
    def _parse_expires(raw: str | None) -> datetime | None:
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _load_token_cache(self) -> None:
        if self._token:
            return
        if not self._cache_path.exists():
            return
        try:
            data = json.loads(self._cache_path.read_text(encoding="utf-8"))
        except Exception:
            return
        token = str(data.get("access_token") or "").strip()
        expires = self._parse_expires(data.get("expires_at"))
        if token:
            self._token = token
            self._token_expires_at = expires

    def _save_token_cache(self, token: str, expires_at: datetime) -> None:
        payload = {
            "access_token": token,
            "expires_at": expires_at.isoformat(),
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        self._cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _validate_credentials(self) -> None:
        if not self.app_key or not self.app_secret:
            raise ValueError("KIS API 설정이 없습니다. .env에 KIS_APP_KEY와 KIS_APP_SECRET을 설정해 주세요.")

    def _is_token_valid(self) -> bool:
        if not self._token:
            return False
        if not self._token_expires_at:
            return True
        now = datetime.now(timezone.utc)
        return self._token_expires_at > now + timedelta(minutes=2)

    def get_access_token(self) -> str:
        if self._is_token_valid() and self._token:
            return self._token
        return self.issue_access_token()

    def issue_access_token(self) -> str:
        self._validate_credentials()
        url = f"{self.base_url}/oauth2/tokenP"
        body: dict[str, Any] = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }
        response = requests.post(url, json=body, timeout=self.timeout)
        text_preview = (response.text or "")[:300]
        if response.status_code >= 400:
            logger.error("[KIS] token issue failed status=%s body=%s", response.status_code, text_preview)
            raise ValueError(f"KIS API 인증 실패(status={response.status_code})")
        data = response.json()
        token = str(data.get("access_token") or "").strip()
        if not token:
            logger.error("[KIS] token missing in response body=%s", text_preview)
            raise ValueError("KIS API 인증 실패: access_token이 응답에 없습니다.")
        expires_in = int(data.get("expires_in") or 86400)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(60, expires_in))
        self._token = token
        self._token_expires_at = expires_at
        self._save_token_cache(token, expires_at)
        return token
