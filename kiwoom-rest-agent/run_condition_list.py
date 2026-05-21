from __future__ import annotations

import argparse
import socket
from datetime import datetime
from pathlib import Path
import os

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


def _diagnose_tcp(host: str, port: int, timeout: int = 5) -> tuple[bool, str | None, str | None]:
    try:
        ip = socket.gethostbyname(host)
    except Exception as exc:
        return False, None, f"dns_resolve_failed: {exc}"

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, ip, None
    except Exception as exc:
        return False, ip, str(exc)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--send-drct", action="store_true")
    parser.add_argument("--diagnose-only", action="store_true")
    parser.add_argument("--header-mode", choices=["full", "auth-only", "none"], default="auth-only")
    parser.add_argument("--login-mode", choices=["header", "message-bearer", "message-token", "none"], default="message-token")
    args = parser.parse_args()

    settings = load_settings()
    print(
        {
            "env_file_path": settings.env_file_path,
            "base_url": settings.base_url,
            "ws_url": settings.ws_url,
            "use_proxy": settings.use_proxy,
            "ws_timeout_seconds": settings.ws_timeout_seconds,
            "header_mode": args.header_mode,
            "login_mode": args.login_mode,
            "proxy_env_exists": _proxy_env_exists(),
        }
    )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    raw_path = AGENT_ROOT / "data" / "raw" / f"condition_list_{ts}.json"
    diag_path = AGENT_ROOT / "data" / "raw" / f"condition_list_diagnostic_{ts}.json"
    norm_path = AGENT_ROOT / "data" / "normalized" / f"condition_list_{ts}.json"

    host = "api.kiwoom.com"
    port = 10000
    tcp_ok, resolved_ip, tcp_error = _diagnose_tcp(host=host, port=port)

    if args.diagnose_only:
        diag_only = {
            "diagnose_only": True,
            "host": host,
            "port": port,
            "resolved_ip": resolved_ip,
            "tcp_connect_success": tcp_ok,
            "error": tcp_error,
        }
        ConditionClient.save_json(diag_path, diag_only)
        print(diag_only)
        print(f"diagnostic 저장: {diag_path}")
        return

    auth = AuthClient(settings)
    cond = ConditionClient(settings)

    diagnostic: dict[str, object] = {
        "success": False,
        "stage": "tcp_diagnose",
        "env_file_path": settings.env_file_path,
        "ws_url": settings.ws_url,
        "use_proxy": settings.use_proxy,
        "proxy_env_exists": _proxy_env_exists(),
        "header_mode": args.header_mode,
        "login_mode": args.login_mode,
        "tcp_connect_success": tcp_ok,
        "resolved_ip": resolved_ip,
        "websocket_connect_success": False,
        "login_success": False,
        "cnsrlst_success": False,
        "login_message_sent": False,
        "login_ack_received": False,
        "cnsrlst_message_sent": False,
        "cnsrlst_response_received": False,
        "condition_count": 0,
        "first_error_code": None,
        "first_error_message": None,
        "failure_reason": None,
        "error_type": None,
        "error_message": None,
        "raw_messages": [],
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    try:
        diagnostic["stage"] = "websocket_connect"
        token = auth.issue_token().token

        diagnostic["stage"] = "login_wait_ack"
        raw = cond.get_condition_list(token=token, header_mode=args.header_mode, login_mode=args.login_mode)
        ConditionClient.save_json(raw_path, raw)

        diagnostic["websocket_connect_success"] = bool(raw.get("websocket_connect_success"))
        diagnostic["login_success"] = bool(raw.get("login_success"))
        diagnostic["cnsrlst_success"] = bool(raw.get("cnsrlst_success"))
        diagnostic["login_message_sent"] = bool(raw.get("login_message_sent"))
        diagnostic["login_ack_received"] = bool(raw.get("login_ack_received"))
        diagnostic["cnsrlst_message_sent"] = bool(raw.get("cnsrlst_message_sent"))
        diagnostic["cnsrlst_response_received"] = bool(raw.get("cnsrlst_response_received"))
        diagnostic["first_error_code"] = raw.get("first_error_code")
        diagnostic["first_error_message"] = raw.get("first_error_message")
        diagnostic["failure_reason"] = raw.get("failure_reason")
        diagnostic["raw_messages"] = raw.get("raw_messages") or []
        diagnostic["stage"] = "cnsrlst_wait_response"

        response = raw.get("response")
        if isinstance(response, dict):
            rc = response.get("return_code")
            rm = response.get("return_msg")
            if rc not in (None, 0, "0", "000000"):
                diagnostic["error_type"] = "kiwoom_return_code"
                diagnostic["error_message"] = f"return_code={rc}, return_msg={rm}"

        diagnostic["stage"] = "normalize"
        items = cond.normalize_condition_list(response if isinstance(response, dict) else {})
        diagnostic["condition_count"] = len(items)

        if len(items) > 0:
            normalized = {"source": "kiwoom_rest", "source_api": "ka10171", "items": items}
            ConditionClient.save_json(norm_path, normalized)
            diagnostic["success"] = True
            diagnostic["stage"] = "success"
            print(
                {
                    "success": True,
                    "login_success": diagnostic["login_success"],
                    "cnsrlst_success": diagnostic["cnsrlst_success"],
                    "condition_count": len(items),
                    "items": items[:10],
                }
            )
            print(f"raw 저장: {raw_path}")
            print(f"normalized 저장: {norm_path}")

            if args.send_drct:
                if not settings.drct_api_enabled:
                    print("DRCT_API_ENABLED=false 상태입니다. 전송을 건너뜁니다.")
                else:
                    client = DrctApiClient(settings)
                    status, body = client.sync_conditions(items)
                    print(f"DrCT sync status={status} body={body}")
        else:
            diagnostic["stage"] = "failed"
            if diagnostic["error_message"] is None:
                diagnostic["error_type"] = "empty_condition_list"
                diagnostic["error_message"] = "CNSRLST 응답은 수신했지만 조건식 목록이 비어 있습니다."
            print(
                {
                    "success": False,
                    "login_success": diagnostic["login_success"],
                    "cnsrlst_success": diagnostic["cnsrlst_success"],
                    "condition_count": 0,
                    "error": diagnostic["error_message"],
                    "failure_reason": diagnostic["failure_reason"],
                }
            )
            print(f"raw 저장: {raw_path}")

    except Exception as exc:
        diagnostic["error_type"] = type(exc).__name__
        diagnostic["error_message"] = str(exc)
        diagnostic["stage"] = "failed"
        print(f"조건검색 목록조회 실패: {exc}")

    finally:
        ConditionClient.save_json(diag_path, diagnostic)
        print(f"diagnostic 저장: {diag_path}")


if __name__ == "__main__":
    main()
