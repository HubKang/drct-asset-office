from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from app.auth_client import AuthClient, KiwoomTokenError
from app.config import load_settings
from app.logger import get_logger, mask_sensitive


def main() -> None:
    logger = get_logger(__name__)
    try:
        settings = load_settings()
    except Exception as exc:
        print(f"[설정 오류] {exc}")
        return

    auth = AuthClient(settings)
    proxy_env_exists = {
        "HTTP_PROXY": bool(os.getenv("HTTP_PROXY")),
        "HTTPS_PROXY": bool(os.getenv("HTTPS_PROXY")),
        "ALL_PROXY": bool(os.getenv("ALL_PROXY")),
    }

    logger.info(
        "Token test env: loaded_env_path=%s base_url=%s use_proxy=%s auth_session_trust_env=%s proxy_env_exists=%s",
        settings.env_file_path,
        settings.base_url,
        settings.use_proxy,
        auth.session.trust_env,
        proxy_env_exists,
    )

    try:
        token_res = auth.issue_token()
        out = {
            "success": True,
            "base_url": settings.base_url,
            "env_file_path": settings.env_file_path,
            "use_proxy": settings.use_proxy,
            "session_trust_env": auth.session.trust_env,
            "proxy_env_exists": proxy_env_exists,
            "token": mask_sensitive(token_res.token),
            "token_type": token_res.token_type,
            "expires_dt": token_res.expires_dt,
            "return_code": token_res.return_code,
            "return_msg": token_res.return_msg,
        }
    except KiwoomTokenError as exc:
        out = {
            "success": False,
            "base_url": settings.base_url,
            "env_file_path": settings.env_file_path,
            "use_proxy": settings.use_proxy,
            "session_trust_env": auth.session.trust_env,
            "proxy_env_exists": proxy_env_exists,
            "return_code": exc.return_code,
            "return_msg": exc.return_msg,
        }
    except Exception as exc:
        out = {
            "success": False,
            "base_url": settings.base_url,
            "env_file_path": settings.env_file_path,
            "use_proxy": settings.use_proxy,
            "session_trust_env": auth.session.trust_env,
            "proxy_env_exists": proxy_env_exists,
            "error": str(exc),
        }

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    p = Path(__file__).resolve().parent / "data" / "raw" / f"token_test_{ts}.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info(
        "Token test finished: success=%s base_url=%s env_file_path=%s use_proxy=%s trust_env=%s",
        out.get("success"),
        out.get("base_url"),
        out.get("env_file_path"),
        out.get("use_proxy"),
        out.get("session_trust_env"),
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
