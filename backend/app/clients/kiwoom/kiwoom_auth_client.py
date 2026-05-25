from __future__ import annotations

import logging
import os

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

    @staticmethod
    def get_access_token() -> str:
        token = (config.KIWOOM_REST_ACCESS_TOKEN or "").strip()
        if token:
            return token
        issued = KiwoomAuthClient.issue_token()
        return issued.token

    @staticmethod
    def _base_url() -> str:
        if config.KIWOOM_REST_USE_MOCK:
            return config.KIWOOM_REST_MOCK_BASE_URL.rstrip("/")
        return config.KIWOOM_REST_BASE_URL.rstrip("/")

    @staticmethod
    def issue_token() -> KiwoomTokenResponse:
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

        url = f"{KiwoomAuthClient._base_url()}/oauth2/token"
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

        expires_at = str(payload.get("expires_dt") or payload.get("expires_at") or "").strip() or None
        token_type = str(payload.get("token_type") or "").strip() or None

        # Runtime env only. Never print/save token raw text.
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

