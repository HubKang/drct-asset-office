from __future__ import annotations

from datetime import datetime
from pathlib import Path

import requests

from .config import Settings
from .logger import get_logger, mask_sensitive, sanitize_payload
from .schemas import TokenResponse


class KiwoomTokenError(RuntimeError):
    def __init__(self, return_code: int | str | None = None, return_msg: str = "", safe_payload: dict | None = None):
        self.return_code = return_code
        self.return_msg = return_msg
        self.safe_payload = safe_payload or {}
        super().__init__(f"키움 REST 토큰 발급 실패: return_code={return_code}, return_msg={return_msg}")


class AuthClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = get_logger(__name__)
        self.session = requests.Session()
        self.session.trust_env = settings.use_proxy

    def issue_token(self) -> TokenResponse:
        url = f"{self.settings.base_url}/oauth2/token"
        headers = {
            "api-id": "au10001",
            "Content-Type": "application/json;charset=UTF-8",
        }
        body = {
            "grant_type": "client_credentials",
            "appkey": self.settings.app_key,
            "secretkey": self.settings.secret_key,
        }

        self.logger.info(
            "Request token: url=%s use_proxy=%s trust_env=%s timeout=%s appkey=%s secretkey=%s body=%s",
            url,
            self.settings.use_proxy,
            self.session.trust_env,
            self.settings.timeout_seconds,
            mask_sensitive(self.settings.app_key),
            mask_sensitive(self.settings.secret_key),
            sanitize_payload(body),
        )
        self.logger.info(
            "Kiwoom auth session: use_proxy=%s trust_env=%s",
            self.settings.use_proxy,
            self.session.trust_env,
        )

        response = self.session.post(url, headers=headers, json=body, timeout=self.settings.timeout_seconds)
        response.raise_for_status()
        payload = response.json()

        token = TokenResponse(
            token=payload.get("token") or payload.get("access_token") or "",
            token_type=str(payload.get("token_type") or ""),
            expires_dt=str(payload.get("expires_dt") or ""),
            return_code=payload.get("return_code"),
            return_msg=str(payload.get("return_msg") or ""),
            raw=payload if isinstance(payload, dict) else {"raw": payload},
        )

        if not token.token:
            raise KiwoomTokenError(
                return_code=token.return_code,
                return_msg=token.return_msg,
                safe_payload=token.safe_dict(),
            )

        self._save_token_response(token)
        return token

    def revoke_token(self, token: str) -> dict:
        url = f"{self.settings.base_url}/oauth2/revoke"
        headers = {
            "api-id": "au10002",
            "Content-Type": "application/json;charset=UTF-8",
        }
        body = {
            "appkey": self.settings.app_key,
            "secretkey": self.settings.secret_key,
            "token": token,
        }

        self.logger.info(
            "Revoke token: url=%s use_proxy=%s trust_env=%s body=%s",
            url,
            self.settings.use_proxy,
            self.session.trust_env,
            sanitize_payload(body),
        )
        response = self.session.post(url, headers=headers, json=body, timeout=self.settings.timeout_seconds)
        response.raise_for_status()
        return response.json()

    def _save_token_response(self, token_response: TokenResponse) -> None:
        root = Path(__file__).resolve().parents[1]
        raw_dir = root / "data" / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        out = token_response.safe_dict()
        if out.get("token") == "***MASKED***" and token_response.token:
            t = str(token_response.token)
            out["token"] = f"{t[:4]}****{t[-4:]}" if len(t) > 8 else "****"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        (raw_dir / f"token_response_{ts}.json").write_text(
            __import__("json").dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
        )
