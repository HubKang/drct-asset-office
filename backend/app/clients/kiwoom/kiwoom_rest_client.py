from __future__ import annotations

import json
import logging
import time
from typing import Any

import requests

from backend.app.clients.kiwoom.kiwoom_auth_client import KiwoomAuthClient
from backend.app.clients.kiwoom.kiwoom_errors import KiwoomApiError, KiwoomErrorCode
from backend.app.clients.kiwoom.kiwoom_models import KiwoomRestRequest, KiwoomRestResponse
from backend.app.clients.kiwoom.kiwoom_rate_limiter import KiwoomRateLimiter
from backend.app.core import config

logger = logging.getLogger(__name__)

BLOCKED_ORDER_API_IDS = {
    "kt10000",
    "kt10001",
    "kt10002",
    "kt10003",
    "kt10006",
    "kt10007",
    "kt10008",
    "kt10009",
}


class KiwoomRestClient:
    def __init__(self) -> None:
        self._timeout_seconds = max(int(config.KIWOOM_REST_TIMEOUT_SECONDS or 10), 1)
        self._rate_limiter = KiwoomRateLimiter(config.KIWOOM_REST_RATE_LIMIT_PER_SECOND)

    @property
    def base_url(self) -> str:
        if config.KIWOOM_REST_USE_MOCK:
            return config.KIWOOM_REST_MOCK_BASE_URL.rstrip("/")
        return config.KIWOOM_REST_BASE_URL.rstrip("/")

    @staticmethod
    def _mask_token(token: str) -> str:
        if not token:
            return ""
        if len(token) <= 8:
            return "****"
        return f"{token[:4]}****{token[-4:]}"

    @staticmethod
    def _assert_order_blocked(api_id: str) -> None:
        if not config.KIWOOM_REST_BLOCK_ORDER_API:
            return
        if api_id.lower() in BLOCKED_ORDER_API_IDS:
            raise KiwoomApiError(
                code=KiwoomErrorCode.KIWOOM_ORDER_API_BLOCKED,
                message=f"Order API blocked: {api_id}",
            )

    def post_json(
        self,
        path: str,
        *,
        api_id: str,
        body: dict[str, Any],
        cont_yn: str | None = None,
        next_key: str | None = None,
    ) -> KiwoomRestResponse:
        request = KiwoomRestRequest(path=path, api_id=api_id, body=body, cont_yn=cont_yn, next_key=next_key)
        return self.request_json(request)

    def request_json(self, request: KiwoomRestRequest) -> KiwoomRestResponse:
        if not config.KIWOOM_REST_ENABLED:
            raise KiwoomApiError(code=KiwoomErrorCode.KIWOOM_DISABLED, message="KIWOOM_REST_ENABLED is false")
        if not request.api_id:
            raise KiwoomApiError(code=KiwoomErrorCode.KIWOOM_API_ID_MISSING, message="api-id is required")

        self._assert_order_blocked(request.api_id)
        token = KiwoomAuthClient.get_access_token()
        if not token:
            raise KiwoomApiError(code=KiwoomErrorCode.KIWOOM_TOKEN_MISSING, message="access token is missing")

        self._rate_limiter.throttle()
        url = f"{self.base_url}/{request.path.lstrip('/')}"
        headers = {
            "authorization": f"Bearer {token}",
            "api-id": request.api_id,
            "content-type": "application/json;charset=UTF-8",
        }
        if request.cont_yn:
            headers["cont-yn"] = request.cont_yn
        if request.next_key:
            headers["next-key"] = request.next_key

        safe_headers = dict(headers)
        safe_headers["authorization"] = f"Bearer {self._mask_token(token)}"
        logger.info("[KIWOOM REST] POST %s headers=%s", url, safe_headers)

        started = time.perf_counter()
        try:
            resp = requests.post(url, headers=headers, data=json.dumps(request.body, ensure_ascii=False), timeout=self._timeout_seconds)
        except requests.RequestException as exc:
            raise KiwoomApiError(
                code=KiwoomErrorCode.KIWOOM_REQUEST_FAILED,
                message=f"{type(exc).__name__}: {exc}",
            ) from exc
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        if resp.status_code == 429:
            raise KiwoomApiError(code=KiwoomErrorCode.KIWOOM_RATE_LIMITED, message="429 Too Many Requests", status_code=429)
        if resp.status_code >= 400:
            preview = (resp.text or "")[:300].replace("\n", " ")
            raise KiwoomApiError(
                code=KiwoomErrorCode.KIWOOM_HTTP_ERROR,
                message=preview,
                status_code=resp.status_code,
                raw_preview=preview,
            )

        try:
            payload = resp.json()
            if payload is None:
                payload = {}
        except ValueError as exc:
            preview = (resp.text or "")[:300].replace("\n", " ")
            raise KiwoomApiError(
                code=KiwoomErrorCode.KIWOOM_JSON_PARSE_FAILED,
                message=str(exc),
                status_code=resp.status_code,
                raw_preview=preview,
            ) from exc

        json_body = payload if isinstance(payload, dict) else {"data": payload}
        if not json_body:
            raise KiwoomApiError(code=KiwoomErrorCode.KIWOOM_EMPTY_RESPONSE, message="empty response body")

        if config.KIWOOM_REST_LOG_RAW_PREVIEW:
            logger.info("[KIWOOM REST] raw_preview=%s", (resp.text or "")[:500].replace("\n", " "))

        return KiwoomRestResponse(
            status_code=resp.status_code,
            headers=dict(resp.headers),
            json_body=json_body,
            raw_text_preview=(resp.text or "")[:500],
            elapsed_ms=elapsed_ms,
            cont_yn=resp.headers.get("cont-yn", "") or "",
            next_key=resp.headers.get("next-key", "") or "",
        )

