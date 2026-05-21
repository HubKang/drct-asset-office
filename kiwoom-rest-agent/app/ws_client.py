from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from typing import Any

import websocket

from .config import Settings
from .logger import get_logger, sanitize_payload


class KiwoomWsClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = get_logger(__name__)

    def request_once(self, token: str, trnm: str, data: dict[str, Any], timeout: int | None = None) -> dict[str, Any]:
        ws_timeout = timeout or self.settings.ws_timeout_seconds
        ws = websocket.create_connection(
            self.settings.ws_url,
            timeout=ws_timeout,
            enable_multithread=True,
            http_proxy_host=None if not self.settings.use_proxy else None,
            http_proxy_port=None if not self.settings.use_proxy else None,
        )
        try:
            message = {"trnm": trnm, "token": token, "data": data}
            self.logger.info("WS send: %s", sanitize_payload(message))
            ws.send(json.dumps(message, ensure_ascii=False))
            raw = ws.recv()
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = {"raw_text": raw}
            return {
                "request": sanitize_payload(message),
                "response": sanitize_payload(parsed if isinstance(parsed, dict) else {"data": parsed}),
            }
        finally:
            ws.close()

    def request_condition_list(
        self,
        token: str,
        header_mode: str = "auth-only",
        login_mode: str = "message-token",
        timeout: int | None = None,
    ) -> dict[str, Any]:
        ws_timeout = timeout or self.settings.ws_timeout_seconds
        headers = self._build_headers(token=token, header_mode=header_mode)
        header_keys = [h.split(":", 1)[0].strip() for h in headers]
        self.logger.info(
            "Connecting WebSocket: ws_url=%s use_proxy=%s timeout=%s header_mode=%s login_mode=%s header_keys=%s",
            self.settings.ws_url,
            self.settings.use_proxy,
            ws_timeout,
            header_mode,
            login_mode,
            header_keys,
        )
        raw_messages: list[dict[str, Any]] = []
        first_error_code: str | int | None = None
        first_error_message: str | None = None
        login_result: dict[str, Any] = {}
        cnsrlst_message: dict[str, Any] | None = None

        with self._temporary_proxy_env_disabled(enabled=not self.settings.use_proxy):
            ws = websocket.create_connection(
                self.settings.ws_url,
                timeout=ws_timeout,
                header=headers,
                enable_multithread=True,
                http_proxy_host=None if not self.settings.use_proxy else None,
                http_proxy_port=None if not self.settings.use_proxy else None,
            )
            try:
                login_result = self.send_login_and_wait_ack(
                    ws=ws,
                    token=token,
                    login_mode=login_mode,
                    raw_messages=raw_messages,
                    timeout=ws_timeout,
                )
                if login_result.get("first_error_code") is not None:
                    first_error_code = login_result.get("first_error_code")
                    first_error_message = login_result.get("first_error_message")

                if login_result.get("login_success"):
                    ws.send(json.dumps({"trnm": "CNSRLST"}, ensure_ascii=False))
                    raw_messages.append({"stage": "cnsrlst_send", "sent": {"trnm": "CNSRLST"}})
                    cnsrlst_message = self.wait_condition_list_response(ws=ws, raw_messages=raw_messages, timeout=ws_timeout)
                    if first_error_code is None and isinstance(cnsrlst_message, dict):
                        rc = cnsrlst_message.get("return_code")
                        rm = cnsrlst_message.get("return_msg")
                        if rc not in (None, 0, "0", "000000"):
                            first_error_code = rc
                            first_error_message = str(rm or "")
            finally:
                ws.close()

        cnsrlst_success = cnsrlst_message is not None and str(cnsrlst_message.get("return_code", "0")) in {"0", "000000"}
        failure_reason = None
        if str(first_error_code) == "100013":
            failure_reason = "LOGIN_REQUIRED_BEFORE_CNSRLST"
        elif login_result.get("login_success") is False:
            failure_reason = login_result.get("failure_reason")

        return {
            "websocket_connect_success": True,
            "login_success": bool(login_result.get("login_success")),
            "cnsrlst_success": cnsrlst_success,
            "header_mode": header_mode,
            "login_mode": login_mode,
            "header_keys": header_keys,
            "response": sanitize_payload(cnsrlst_message) if cnsrlst_message else None,
            "raw_messages": raw_messages,
            "login_message_sent": bool(login_result.get("login_message_sent")),
            "login_ack_received": bool(login_result.get("login_ack_received")),
            "cnsrlst_message_sent": bool(login_result.get("login_success")),
            "cnsrlst_response_received": cnsrlst_message is not None,
            "login_return_code": login_result.get("login_return_code"),
            "login_return_msg": login_result.get("login_return_msg"),
            "first_error_code": first_error_code,
            "first_error_message": first_error_message,
            "failure_reason": failure_reason,
        }

    def request_condition_once(
        self,
        token: str,
        condition_seq: str,
        condition_name: str | None = None,
        header_mode: str = "auth-only",
        login_mode: str = "message-token",
        search_type: str = "0",
        stex_tp: str = "K",
        timeout: int | None = None,
    ) -> dict[str, Any]:
        ws_timeout = timeout or self.settings.ws_timeout_seconds
        headers = self._build_headers(token=token, header_mode=header_mode)
        header_keys = [h.split(":", 1)[0].strip() for h in headers]
        self.logger.info(
            "Connecting WebSocket for CNSRREQ: ws_url=%s use_proxy=%s timeout=%s header_mode=%s login_mode=%s condition_seq=%s",
            self.settings.ws_url,
            self.settings.use_proxy,
            ws_timeout,
            header_mode,
            login_mode,
            condition_seq,
        )

        raw_messages: list[dict[str, Any]] = []
        first_error_code: str | int | None = None
        first_error_message: str | None = None
        login_result: dict[str, Any] = {}
        cnsrreq_message: dict[str, Any] | None = None

        with self._temporary_proxy_env_disabled(enabled=not self.settings.use_proxy):
            ws = websocket.create_connection(
                self.settings.ws_url,
                timeout=ws_timeout,
                header=headers,
                enable_multithread=True,
                http_proxy_host=None if not self.settings.use_proxy else None,
                http_proxy_port=None if not self.settings.use_proxy else None,
            )
            try:
                login_result = self.send_login_and_wait_ack(
                    ws=ws,
                    token=token,
                    login_mode=login_mode,
                    raw_messages=raw_messages,
                    timeout=ws_timeout,
                )
                if login_result.get("first_error_code") is not None:
                    first_error_code = login_result.get("first_error_code")
                    first_error_message = login_result.get("first_error_message")

                if login_result.get("login_success"):
                    ws.send(json.dumps({"trnm": "CNSRLST"}, ensure_ascii=False))
                    raw_messages.append({"stage": "cnsrlst_send", "sent": {"trnm": "CNSRLST"}})
                    _ = self.wait_condition_list_response(ws=ws, raw_messages=raw_messages, timeout=ws_timeout)

                    req_msg: dict[str, Any] = {
                        "trnm": "CNSRREQ",
                        "seq": str(condition_seq),
                        "search_type": str(search_type),
                        "stex_tp": str(stex_tp),
                        "cont_yn": "N",
                        "next_key": "",
                    }
                    if condition_name:
                        req_msg["condition_name"] = str(condition_name)
                    ws.send(json.dumps(req_msg, ensure_ascii=False))
                    raw_messages.append({"stage": "cnsrreq_send", "sent": req_msg})
                    cnsrreq_message = self.wait_condition_once_response(ws=ws, raw_messages=raw_messages, timeout=ws_timeout)
                    if first_error_code is None and isinstance(cnsrreq_message, dict):
                        rc = cnsrreq_message.get("return_code")
                        rm = cnsrreq_message.get("return_msg")
                        if rc not in (None, 0, "0", "000000"):
                            first_error_code = rc
                            first_error_message = str(rm or "")
            finally:
                ws.close()

        cnsrreq_success = cnsrreq_message is not None and str(cnsrreq_message.get("return_code", "0")) in {"0", "000000"}
        failure_reason = None
        if str(first_error_code) == "100013":
            failure_reason = "LOGIN_REQUIRED_BEFORE_CNSRREQ"
        elif login_result.get("login_success") is False:
            failure_reason = login_result.get("failure_reason")
        elif not cnsrreq_success:
            failure_reason = "CNSRREQ_RESPONSE_NOT_FOUND_OR_ERROR"

        return {
            "success": bool(login_result.get("login_success")) and cnsrreq_message is not None,
            "stage": "success" if (bool(login_result.get("login_success")) and cnsrreq_message is not None) else "failed",
            "websocket_connect_success": True,
            "login_success": bool(login_result.get("login_success")),
            "cnsrreq_success": cnsrreq_success,
            "condition_seq": str(condition_seq),
            "condition_name": condition_name,
            "header_mode": header_mode,
            "login_mode": login_mode,
            "search_type": str(search_type),
            "stex_tp": str(stex_tp),
            "header_keys": header_keys,
            "response": sanitize_payload(cnsrreq_message) if cnsrreq_message else None,
            "raw_messages": raw_messages,
            "login_message_sent": bool(login_result.get("login_message_sent")),
            "login_ack_received": bool(login_result.get("login_ack_received")),
            "cnsrreq_message_sent": bool(login_result.get("login_success")),
            "cnsrreq_response_received": cnsrreq_message is not None,
            "login_return_code": login_result.get("login_return_code"),
            "login_return_msg": login_result.get("login_return_msg"),
            "first_error_code": first_error_code,
            "first_error_message": first_error_message,
            "failure_reason": failure_reason,
        }

    def send_login_and_wait_ack(
        self,
        ws: Any,
        token: str,
        login_mode: str,
        raw_messages: list[dict[str, Any]],
        timeout: int,
        max_messages: int = 20,
    ) -> dict[str, Any]:
        login_message_sent = False
        login_ack_received = False
        login_return_code: str | int | None = None
        login_return_msg: str | None = None
        first_error_code: str | int | None = None
        first_error_message: str | None = None
        failure_reason: str | None = None

        if login_mode in {"message-token", "message-bearer"}:
            login_token = token if login_mode == "message-token" else f"Bearer {token}"
            login_msg = {"trnm": "LOGIN", "token": login_token}
            ws.send(json.dumps(login_msg, ensure_ascii=False))
            raw_messages.append({"stage": "login_send", "sent": {"trnm": "LOGIN", "token": "***MASKED***"}})
            login_message_sent = True

        deadline = time.time() + timeout
        while len(raw_messages) < max_messages and time.time() < deadline:
            raw = ws.recv()
            try:
                msg = json.loads(raw)
            except Exception:
                msg = {"raw_text": raw}
            sanitized = sanitize_payload(msg if isinstance(msg, dict) else {"data": msg})
            raw_messages.append({"stage": "login_wait_ack", "received": sanitized})

            if not isinstance(msg, dict):
                continue
            trnm = str(msg.get("trnm") or "").upper()
            if trnm == "PING":
                ws.send(json.dumps(msg, ensure_ascii=False))
                raw_messages.append({"stage": "login_wait_ack", "sent": {"trnm": "PING"}})
                continue
            rc = msg.get("return_code")
            rm = str(msg.get("return_msg") or msg.get("message") or "")
            login_like = trnm == "LOGIN" or "LOGIN" in trnm

            if login_like:
                login_ack_received = True
                login_return_code = rc
                login_return_msg = rm
                if str(rc) in {"0", "000000"} or "정상" in rm:
                    return {
                        "login_success": True,
                        "login_message_sent": login_message_sent,
                        "login_ack_received": True,
                        "login_return_code": login_return_code,
                        "login_return_msg": login_return_msg,
                        "first_error_code": first_error_code,
                        "first_error_message": first_error_message,
                        "failure_reason": None,
                    }
                if first_error_code is None and rc not in (None, 0, "0", "000000"):
                    first_error_code = rc
                    first_error_message = rm
                failure_reason = "LOGIN_ACK_ERROR"
                return {
                    "login_success": False,
                    "login_message_sent": login_message_sent,
                    "login_ack_received": login_ack_received,
                    "login_return_code": login_return_code,
                    "login_return_msg": login_return_msg,
                    "first_error_code": first_error_code,
                    "first_error_message": first_error_message,
                    "failure_reason": failure_reason,
                }

            if first_error_code is None and rc not in (None, 0, "0", "000000"):
                first_error_code = rc
                first_error_message = rm
                if str(rc) == "100013":
                    failure_reason = "LOGIN_REQUIRED_BEFORE_CNSRLST"
                    return {
                        "login_success": False,
                        "login_message_sent": login_message_sent,
                        "login_ack_received": login_ack_received,
                        "login_return_code": login_return_code,
                        "login_return_msg": login_return_msg,
                        "first_error_code": first_error_code,
                        "first_error_message": first_error_message,
                        "failure_reason": failure_reason,
                    }

        if login_mode == "header":
            failure_reason = "LOGIN_ACK_NOT_RECEIVED_HEADER_MODE"
        else:
            failure_reason = "LOGIN_ACK_TIMEOUT"
        return {
            "login_success": False,
            "login_message_sent": login_message_sent,
            "login_ack_received": login_ack_received,
            "login_return_code": login_return_code,
            "login_return_msg": login_return_msg,
            "first_error_code": first_error_code,
            "first_error_message": first_error_message,
            "failure_reason": failure_reason,
        }

    def wait_condition_list_response(
        self,
        ws: Any,
        raw_messages: list[dict[str, Any]],
        timeout: int,
        max_messages: int = 40,
    ) -> dict[str, Any] | None:
        deadline = time.time() + timeout
        while len(raw_messages) < max_messages and time.time() < deadline:
            raw = ws.recv()
            try:
                msg = json.loads(raw)
            except Exception:
                msg = {"raw_text": raw}
            sanitized = sanitize_payload(msg if isinstance(msg, dict) else {"data": msg})
            raw_messages.append({"stage": "cnsrlst_wait_response", "received": sanitized})
            if isinstance(msg, dict) and str(msg.get("trnm") or "").upper() == "PING":
                ws.send(json.dumps(msg, ensure_ascii=False))
                raw_messages.append({"stage": "cnsrlst_wait_response", "sent": {"trnm": "PING"}})
                continue
            if isinstance(msg, dict) and str(msg.get("trnm") or "").upper() == "CNSRLST":
                return msg
        return None

    def wait_condition_once_response(
        self,
        ws: Any,
        raw_messages: list[dict[str, Any]],
        timeout: int,
        max_messages: int = 30,
    ) -> dict[str, Any] | None:
        deadline = time.time() + timeout
        while len(raw_messages) < max_messages and time.time() < deadline:
            raw = ws.recv()
            try:
                msg = json.loads(raw)
            except Exception:
                msg = {"raw_text": raw}
            sanitized = sanitize_payload(msg if isinstance(msg, dict) else {"data": msg})
            raw_messages.append({"stage": "cnsrreq_wait_response", "received": sanitized})
            if not isinstance(msg, dict):
                continue
            trnm = str(msg.get("trnm") or "").upper()
            if trnm == "PING":
                ws.send(json.dumps(msg, ensure_ascii=False))
                raw_messages.append({"stage": "cnsrreq_wait_response", "sent": {"trnm": "PING"}})
                continue
            if trnm == "CNSRREQ":
                return msg
            if msg.get("data") is not None and msg.get("return_code") in (None, 0, "0", "000000"):
                return msg
            rc = msg.get("return_code")
            if rc not in (None, 0, "0", "000000"):
                return msg
        return None

    def _build_headers(self, token: str, header_mode: str) -> list[str]:
        if header_mode == "none":
            return []
        if header_mode == "auth-only":
            return [f"authorization: Bearer {token}"]
        return [
            "api-id: ka10171",
            f"authorization: Bearer {token}",
            "Content-Type: application/json;charset=UTF-8",
        ]

    @contextmanager
    def _temporary_proxy_env_disabled(self, enabled: bool):
        if not enabled:
            yield
            return
        keys = ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]
        backup: dict[str, str] = {}
        for key in keys:
            if key in os.environ:
                backup[key] = os.environ[key]
                del os.environ[key]
        try:
            yield
        finally:
            for key, value in backup.items():
                os.environ[key] = value
