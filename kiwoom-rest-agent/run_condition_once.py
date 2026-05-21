from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

from app.auth_client import AuthClient
from app.condition_client import ConditionClient
from app.config import load_settings
from app.drct_api_client import DrctApiClient

AGENT_ROOT = Path(__file__).resolve().parent


def _proxy_env_exists() -> dict[str, bool]:
    return {
        "HTTP_PROXY": bool(os.getenv("HTTP_PROXY")),
        "HTTPS_PROXY": bool(os.getenv("HTTPS_PROXY")),
        "ALL_PROXY": bool(os.getenv("ALL_PROXY")),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition-seq", required=True)
    parser.add_argument("--condition-name", default="")
    parser.add_argument("--send-drct", action="store_true")
    parser.add_argument("--header-mode", choices=["full", "auth-only", "none"], default="auth-only")
    parser.add_argument("--login-mode", choices=["header", "message-bearer", "message-token"], default="message-token")
    parser.add_argument("--search-type", default="0")
    parser.add_argument("--stex-tp", default="K")
    parser.add_argument("--json-output", action="store_true")
    args = parser.parse_args()

    settings = load_settings()
    print(
        {
            "env_file_path": settings.env_file_path,
            "ws_url": settings.ws_url,
            "use_proxy": settings.use_proxy,
            "header_mode": args.header_mode,
            "login_mode": args.login_mode,
            "condition_seq": args.condition_seq,
            "condition_name": args.condition_name,
            "search_type": args.search_type,
            "stex_tp": args.stex_tp,
            "proxy_env_exists": _proxy_env_exists(),
        }
    )

    auth = AuthClient(settings)
    cond = ConditionClient(settings)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    raw_path = AGENT_ROOT / "data" / "raw" / f"condition_result_{args.condition_seq}_{ts}.json"
    diag_path = AGENT_ROOT / "data" / "raw" / f"condition_result_diagnostic_{args.condition_seq}_{ts}.json"
    norm_path = AGENT_ROOT / "data" / "normalized" / f"condition_result_{args.condition_seq}_{ts}.json"

    diagnostic: dict[str, object] = {
        "success": False,
        "stage": "websocket_connect",
        "env_file_path": settings.env_file_path,
        "ws_url": settings.ws_url,
        "condition_seq": str(args.condition_seq),
        "condition_name": args.condition_name or None,
        "use_proxy": settings.use_proxy,
        "header_mode": args.header_mode,
        "login_mode": args.login_mode,
        "search_type": str(args.search_type),
        "stex_tp": str(args.stex_tp),
        "proxy_env_exists": _proxy_env_exists(),
        "login_success": False,
        "cnsrreq_success": False,
        "item_count": 0,
        "error_type": None,
        "error_message": None,
        "failure_reason": None,
        "first_error_code": None,
        "first_error_message": None,
        "raw_messages": [],
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    summary: dict[str, object] = {
        "success": False,
        "condition_seq": str(args.condition_seq),
        "condition_name": args.condition_name or None,
        "login_success": False,
        "cnsrreq_success": False,
        "item_count": 0,
        "items": [],
    }

    try:
        token = auth.issue_token().token
        diagnostic["stage"] = "login_wait_ack"
        raw = cond.get_condition_once(
            token=token,
            seq=str(args.condition_seq),
            condition_name=args.condition_name or None,
            header_mode=args.header_mode,
            login_mode=args.login_mode,
            search_type=str(args.search_type),
            stex_tp=str(args.stex_tp),
        )
        ConditionClient.save_json(raw_path, raw)

        diagnostic["login_success"] = bool(raw.get("login_success"))
        diagnostic["cnsrreq_success"] = bool(raw.get("cnsrreq_success"))
        diagnostic["raw_messages"] = raw.get("raw_messages") or []
        diagnostic["failure_reason"] = raw.get("failure_reason")
        diagnostic["first_error_code"] = raw.get("first_error_code")
        diagnostic["first_error_message"] = raw.get("first_error_message")
        diagnostic["stage"] = "normalize"

        response = raw.get("response")
        items = cond.normalize_condition_result(
            raw={"response": response} if isinstance(response, dict) else {},
            condition_seq=str(args.condition_seq),
            condition_name=args.condition_name or None,
        )
        diagnostic["item_count"] = len(items)

        if bool(raw.get("login_success")) and bool(raw.get("cnsrreq_success")):
            normalized = {
                "source": "kiwoom_rest",
                "source_api": "ka10172",
                "condition_seq": str(args.condition_seq),
                "condition_name": args.condition_name or None,
                "items": items,
            }
            ConditionClient.save_json(norm_path, normalized)
            diagnostic["success"] = True
            diagnostic["stage"] = "success"
            summary = {
                "success": True,
                "condition_seq": str(args.condition_seq),
                "condition_name": args.condition_name or None,
                "login_success": True,
                "cnsrreq_success": True,
                "item_count": len(items),
                "items": items,
            }
            print(summary)
            print(f"raw saved: {raw_path}")
            print(f"normalized saved: {norm_path}")
            if args.send_drct:
                if not settings.drct_api_enabled:
                    print("DRCT_API_ENABLED=false; skip DRCT save")
                elif len(items) == 0:
                    print("No condition result items; skip DRCT save")
                else:
                    client = DrctApiClient(settings)
                    status, body = client.save_condition_results(str(args.condition_seq), args.condition_name or None, items)
                    print(f"DrCT result save status={status} body={body}")
        else:
            diagnostic["stage"] = "failed"
            diagnostic["error_type"] = "cnsrreq_failed"
            diagnostic["error_message"] = f"login_success={raw.get('login_success')} cnsrreq_success={raw.get('cnsrreq_success')}"
            summary = {
                "success": False,
                "condition_seq": str(args.condition_seq),
                "condition_name": args.condition_name or None,
                "login_success": bool(raw.get("login_success")),
                "cnsrreq_success": bool(raw.get("cnsrreq_success")),
                "item_count": len(items),
                "error": diagnostic["error_message"],
                "failure_reason": diagnostic["failure_reason"],
                "items": items,
            }
            print(summary)
            print(f"raw saved: {raw_path}")
    except Exception as exc:
        diagnostic["stage"] = "failed"
        diagnostic["error_type"] = type(exc).__name__
        diagnostic["error_message"] = str(exc)
        summary = {
            "success": False,
            "condition_seq": str(args.condition_seq),
            "condition_name": args.condition_name or None,
            "login_success": False,
            "cnsrreq_success": False,
            "item_count": 0,
            "error": str(exc),
            "items": [],
        }
        print(f"condition once failed: {exc}")
    finally:
        ConditionClient.save_json(diag_path, diagnostic)
        print(f"diagnostic saved: {diag_path}")
        if args.json_output:
            print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
