from __future__ import annotations

from dataclasses import dataclass

import requests

from .config import Settings
from .logger import get_logger, sanitize_payload


BLOCKED_ORDER_API_IDS = {
    "kt10000", "kt10001", "kt10002", "kt10003", "kt10006", "kt10007", "kt10008", "kt10009"
}


@dataclass
class RestApiResult:
    status_code: int
    headers: dict
    body: dict
    cont_yn: str | None
    next_key: str | None


class KiwoomRestClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = get_logger(__name__)
        self.session = requests.Session()
        self.session.trust_env = settings.use_proxy
        self.logger.info(
            "Kiwoom rest session init: use_proxy=%s trust_env=%s",
            self.settings.use_proxy,
            self.session.trust_env,
        )

    def post(
        self,
        api_id: str,
        path: str,
        body: dict,
        token: str,
        cont_yn: str | None = None,
        next_key: str | None = None,
    ) -> RestApiResult:
        if api_id.lower() in BLOCKED_ORDER_API_IDS:
            raise PermissionError("DrCT Kiwoom REST Agent는 조회 전용입니다. 주문 API 호출은 차단되었습니다.")

        headers = {
            "api-id": api_id,
            "authorization": f"Bearer {token}",
            "Content-Type": "application/json;charset=UTF-8",
        }
        if cont_yn:
            headers["cont-yn"] = cont_yn
        if next_key:
            headers["next-key"] = next_key

        safe_headers = dict(headers)
        safe_headers["authorization"] = "Bearer ****"

        url = f"{self.settings.base_url}{path}"
        self.logger.info(
            "POST %s use_proxy=%s trust_env=%s headers=%s body=%s",
            url,
            self.settings.use_proxy,
            self.session.trust_env,
            safe_headers,
            sanitize_payload(body),
        )

        response = self.session.post(url, headers=headers, json=body, timeout=self.settings.timeout_seconds)
        status_code = response.status_code

        try:
            payload = response.json()
        except Exception:
            payload = {"raw_text": response.text}

        if status_code >= 400:
            raise requests.HTTPError(f"HTTP {status_code}: {payload}")

        return RestApiResult(
            status_code=status_code,
            headers=dict(response.headers),
            body=payload if isinstance(payload, dict) else {"data": payload},
            cont_yn=response.headers.get("cont-yn"),
            next_key=response.headers.get("next-key"),
        )
