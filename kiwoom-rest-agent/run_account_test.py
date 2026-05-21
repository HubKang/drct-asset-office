from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from app.account_client import AccountClient
from app.auth_client import AuthClient, KiwoomTokenError
from app.config import load_settings
from app.kiwoom_rest_client import KiwoomRestClient
from app.logger import get_logger


def mask_account(acc: str) -> str:
    acc = (acc or "").strip()
    if len(acc) < 4:
        return "****"
    return f"{acc[:2]}****{acc[-2:]}"


def main() -> None:
    logger = get_logger(__name__)
    try:
        settings = load_settings()
    except Exception as exc:
        print(f"[설정 오류] {exc}")
        return

    auth = AuthClient(settings)
    rest = KiwoomRestClient(settings)
    account_client = AccountClient(rest)

    proxy_env_exists = {
        "HTTP_PROXY": bool(os.getenv("HTTP_PROXY")),
        "HTTPS_PROXY": bool(os.getenv("HTTPS_PROXY")),
        "ALL_PROXY": bool(os.getenv("ALL_PROXY")),
    }

    result_out: dict = {
        "base_url": settings.base_url,
        "env_file_path": settings.env_file_path,
        "use_proxy": settings.use_proxy,
        "auth_session_trust_env": auth.session.trust_env,
        "rest_session_trust_env": rest.session.trust_env,
        "proxy_env_exists": proxy_env_exists,
        "token_issue": {"success": False},
        "account_query": {"success": False},
    }

    try:
        token_res = auth.issue_token()
        result_out["token_issue"] = {
            "success": True,
            "return_code": token_res.return_code,
            "return_msg": token_res.return_msg,
            "expires_dt": token_res.expires_dt,
        }
    except KiwoomTokenError as exc:
        result_out["token_issue"] = {
            "success": False,
            "return_code": exc.return_code,
            "return_msg": exc.return_msg,
        }
        logger.info("Account test finished: token issue failed")
        print(json.dumps(result_out, ensure_ascii=False, indent=2))
        return
    except Exception as exc:
        result_out["token_issue"] = {
            "success": False,
            "error": str(exc),
        }
        logger.info("Account test finished: token issue failed")
        print(json.dumps(result_out, ensure_ascii=False, indent=2))
        return

    try:
        api_result = account_client.get_account_no(token_res.token)
        body = api_result.body
        masked_body = json.loads(json.dumps(body, ensure_ascii=False))
        for k in list(masked_body.keys()):
            kl = k.lower()
            if ("acnt" in kl) or ("account" in kl) or ("acct" in kl):
                v = masked_body.get(k)
                if isinstance(v, str):
                    masked_body[k] = mask_account(v)
                elif isinstance(v, list):
                    masked_body[k] = [mask_account(str(x)) for x in v]

        result_out["account_query"] = {
            "success": True,
            "status_code": api_result.status_code,
            "body": masked_body,
        }
    except Exception as exc:
        result_out["account_query"] = {
            "success": False,
            "error": str(exc),
        }

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    p = Path(__file__).resolve().parent / "data" / "raw" / f"account_test_{ts}.json"
    p.write_text(json.dumps(result_out, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info(
        "Account test finished: token_success=%s account_success=%s use_proxy=%s auth_trust_env=%s rest_trust_env=%s",
        result_out["token_issue"].get("success"),
        result_out["account_query"].get("success"),
        settings.use_proxy,
        auth.session.trust_env,
        rest.session.trust_env,
    )
    print(json.dumps(result_out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
