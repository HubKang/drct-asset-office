from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.clients.kiwoom.kiwoom_auth_client import KiwoomAuthClient
from backend.app.clients.kiwoom.kiwoom_errors import KiwoomApiError
from backend.app.core import config


def main() -> int:
    try:
        token_resp = KiwoomAuthClient.issue_token()
        out = {
            "success": True,
            "enabled": bool(config.KIWOOM_REST_ENABLED),
            "use_mock": bool(config.KIWOOM_REST_USE_MOCK),
            "base_url": config.KIWOOM_REST_MOCK_BASE_URL if config.KIWOOM_REST_USE_MOCK else config.KIWOOM_REST_BASE_URL,
            "app_key_present": bool(config.KIWOOM_REST_APP_KEY),
            "secret_key_present": bool(config.KIWOOM_REST_SECRET_KEY),
            "access_token_present": bool(token_resp.token),
            "token_type": token_resp.token_type,
            "expires_at": token_resp.expires_at,
            "return_code": token_resp.raw.get("return_code"),
            "return_msg": token_resp.raw.get("return_msg"),
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    except KiwoomApiError as exc:
        out = {
            "success": False,
            "enabled": bool(config.KIWOOM_REST_ENABLED),
            "use_mock": bool(config.KIWOOM_REST_USE_MOCK),
            "base_url": config.KIWOOM_REST_MOCK_BASE_URL if config.KIWOOM_REST_USE_MOCK else config.KIWOOM_REST_BASE_URL,
            "app_key_present": bool(config.KIWOOM_REST_APP_KEY),
            "secret_key_present": bool(config.KIWOOM_REST_SECRET_KEY),
            "error_code": exc.code,
            "error_message": exc.message,
            "status_code": exc.status_code,
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

