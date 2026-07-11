from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime

import requests

from backend.app.clients.kiwoom.kiwoom_errors import KiwoomApiError, KiwoomErrorCode
from backend.app.clients.kiwoom.kiwoom_models import KiwoomTokenResponse
from backend.app.core import config

logger = logging.getLogger(__name__)


class KiwoomAuthClient:
    """Kiwoom OAuth2 token helper.

    Priority:
    1) Use KIWOOM_REST_ACCESS_TOKEN when present
    2) Otherwise issue token with appkey/secretkey
    """

    _lock = threading.Lock()
    _cached_access_token: str | None = None
    _cached_expires_at_epoch: float | None = None
    _token_expiry_margin_seconds = 60
    _fallback_token_ttl_seconds = 30 * 60
    _auth_token_issue_count = 0

    @classmethod
    def get_access_token(cls, *, force_refresh: bool = False) -> str:
        token = (config.KIWOOM_REST_ACCESS_TOKEN or "").strip()
        if token and not force_refresh:
            return token

        with cls._lock:
            if not force_refresh and cls._is_cached_token_valid():
                return cls._cached_access_token or ""
            issued = cls.issue_token()
            return issued.token

    @classmethod
    def _is_cached_token_valid(cls) -> bool:
        if not cls._cached_access_token:
            return False
        if cls._cached_expires_at_epoch is None:
            return True
        return time.time() < cls._cached_expires_at_epoch - cls._token_expiry_margin_seconds

    @classmethod
    def _resolve_expires_at_epoch(cls, payload: dict[str, object]) -> tuple[float, str | None]:
        expires_in = payload.get("expires_in")
        try:
            ttl = int(float(str(expires_in).strip())) if expires_in is not None else None
        except Exception:
            ttl = None
        if ttl and ttl > 0:
            return time.time() + ttl, None

        raw_expires_at = str(payload.get("expires_dt") or payload.get("expires_at") or "").strip()
        if raw_expires_at:
            parsed = cls._parse_expires_at(raw_expires_at)
            if parsed is not None:
                return parsed, raw_expires_at

        return time.time() + cls._fallback_token_ttl_seconds, raw_expires_at or None

    @staticmethod
    def _parse_expires_at(raw: str) -> float | None:
        normalized = raw.strip()
        candidates = [
            "%Y%m%d%H%M%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
        ]
        for fmt in candidates:
            try:
                return datetime.strptime(normalized[:19] if "%Y-%m-%d" in fmt else normalized, fmt).timestamp()
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(normalized.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None

    @classmethod
    def diagnostics_snapshot(cls) -> dict[str, int]:
        with cls._lock:
            return {"auth_token_issue_count": cls._auth_token_issue_count}

    @staticmethod
    def _base_url() -> str:
        if config.KIWOOM_REST_USE_MOCK:
            return config.KIWOOM_REST_MOCK_BASE_URL.rstrip("/")
        return config.KIWOOM_REST_BASE_URL.rstrip("/")

    @classmethod
    def issue_token(cls) -> KiwoomTokenResponse:
        if not config.KIWOOM_REST_ENABLED:
            raise KiwoomApiError(
                code=KiwoomErrorCode.KIWOOM_DISABLED,
                message="KIWOOM_REST_ENABLED is false",
            )

        app_key = (config.KIWOOM_REST_APP_KEY or "").strip()
        secret_key = (config.KIWOOM_REST_SECRET_KEY or "").strip()
        if not app_key or not secret_key:
            raise KiwoomApiError(
                code=KiwoomErrorCode.KIWOOM_TOKEN_MISSING,
                message="appkey/secretkey missing",
            )

        url = f"{cls._base_url()}/oauth2/token"
        headers = {"Content-Type": "application/json;charset=UTF-8"}
        body = {
            "grant_type": "client_credentials",
            "appkey": app_key,
            "secretkey": secret_key,
        }

        logger.info(
            "[KIWOOM AUTH] issue token url=%s use_mock=%s appkey_present=%s secret_present=%s",
            url,
            config.KIWOOM_REST_USE_MOCK,
            True,
            True,
        )

        try:
            response = requests.post(
                url,
                headers=headers,
                json=body,
                timeout=max(int(config.KIWOOM_REST_TIMEOUT_SECONDS or 10), 1),
            )
        except requests.RequestException as exc:
            raise KiwoomApiError(
                code=KiwoomErrorCode.KIWOOM_REQUEST_FAILED,
                message=f"{type(exc).__name__}: {exc}",
            ) from exc

        if response.status_code >= 400:
            preview = (response.text or "")[:300].replace("\n", " ")
            raise KiwoomApiError(
                code=KiwoomErrorCode.KIWOOM_HTTP_ERROR,
                message=preview,
                status_code=response.status_code,
                raw_preview=preview,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            preview = (response.text or "")[:300].replace("\n", " ")
            raise KiwoomApiError(
                code=KiwoomErrorCode.KIWOOM_JSON_PARSE_FAILED,
                message=str(exc),
                status_code=response.status_code,
                raw_preview=preview,
            ) from exc

        if not isinstance(payload, dict):
            raise KiwoomApiError(
                code=KiwoomErrorCode.KIWOOM_JSON_PARSE_FAILED,
                message="token response is not object",
            )

        token = str(payload.get("token") or payload.get("access_token") or "").strip()
        if not token:
            ret_code = str(payload.get("return_code") or payload.get("code") or "")
            ret_msg = str(payload.get("return_msg") or payload.get("message") or "token missing in response")
            raise KiwoomApiError(
                code=KiwoomErrorCode.KIWOOM_API_ERROR,
                message=f"{ret_code}:{ret_msg}" if ret_code else ret_msg,
                status_code=response.status_code,
                raw_preview=(response.text or "")[:300],
            )

        expires_at_epoch, expires_at = cls._resolve_expires_at_epoch(payload)
        token_type = str(payload.get("token_type") or "").strip() or None

        # Runtime env only. Never print/save token raw text.
        cls._cached_access_token = token
        cls._cached_expires_at_epoch = expires_at_epoch
        cls._auth_token_issue_count += 1
        os.environ["KIWOOM_REST_ACCESS_TOKEN"] = token
        if expires_at:
            os.environ["KIWOOM_REST_TOKEN_EXPIRES_AT"] = expires_at

        logger.info(
            "[KIWOOM AUTH] token issued token_present=%s expires_present=%s",
            True,
            bool(expires_at),
        )

        return KiwoomTokenResponse(
            token=token,
            token_type=token_type,
            expires_at=expires_at,
            raw=payload,
        )

