from __future__ import annotations

from datetime import datetime
import json
import os
import time
from typing import Any
from contextlib import contextmanager

import websocket

from backend.app.clients.kiwoom import KiwoomApiError, KiwoomRestClient
from backend.app.clients.kiwoom.kiwoom_auth_client import KiwoomAuthClient
from backend.app.core.config import now_kst


class KiwoomRestConditionProvider:
    def __init__(self) -> None:
        self.client = KiwoomRestClient()
        self.condition_list_path = "/api/dostk/condition"
        self.condition_result_path = "/api/dostk/condition"
        self.ws_url = os.getenv("KIWOOM_WS_URL", "wss://api.kiwoom.com:10000/api/dostk/websocket").strip()
        self.ws_timeout_seconds = int(os.getenv("KIWOOM_WS_TIMEOUT_SECONDS", "12"))
        self.ws_use_proxy = os.getenv("KIWOOM_REST_USE_PROXY", "false").strip().lower() in {"1", "true", "yes", "y", "on"}

    def fetch_condition_list(self) -> dict[str, Any]:
        payload = self._fetch_condition_list_via_ws()
        conditions = self._normalize_condition_list(payload)
        return {
            "source": "kiwoom_rest",
            "api_id": "ka10171",
            "fetched_at": now_kst(),
            "return_code": self._to_str_or_none(payload.get("return_code")),
            "return_msg": self._to_str_or_none(payload.get("return_msg")),
            "condition_count": len(conditions),
            "conditions": conditions,
            "top_level_keys": list(payload.keys()),
            "raw_response_preview": payload,
        }

    def _fetch_condition_list_via_ws(self) -> dict[str, Any]:
        token = KiwoomAuthClient.get_access_token()
        raw_messages: list[dict[str, Any]] = []
        with self._temporary_proxy_env_disabled(enabled=not self.ws_use_proxy):
            ws = websocket.create_connection(
                self.ws_url,
                timeout=max(self.ws_timeout_seconds, 5),
                header=[f"authorization: Bearer {token}"],
                enable_multithread=True,
                http_proxy_host=None if not self.ws_use_proxy else None,
                http_proxy_port=None if not self.ws_use_proxy else None,
            )
            try:
                ws.send(json.dumps({"trnm": "LOGIN", "token": token}, ensure_ascii=False))
                login_msg = self._wait_for_message(ws, timeout=self.ws_timeout_seconds, stages=raw_messages, stage="login_wait_ack", target_trnm="LOGIN")
                if not isinstance(login_msg, dict):
                    return {"return_code": "1", "return_msg": "LOGIN ACK를 수신하지 못했습니다.", "raw_messages": raw_messages}
                login_code = login_msg.get("return_code")
                if str(login_code) not in {"0", "000000"}:
                    return {
                        "return_code": str(login_code),
                        "return_msg": str(login_msg.get("return_msg") or "LOGIN 실패"),
                        "raw_messages": raw_messages,
                    }
                ws.send(json.dumps({"trnm": "CNSRLST"}, ensure_ascii=False))
                cnsrlst_msg = self._wait_for_message(ws, timeout=self.ws_timeout_seconds, stages=raw_messages, stage="cnsrlst_wait_response", target_trnm="CNSRLST")
                if isinstance(cnsrlst_msg, dict):
                    cnsrlst_msg["raw_messages"] = raw_messages
                    return cnsrlst_msg
                return {"return_code": "1", "return_msg": "CNSRLST 응답을 수신하지 못했습니다.", "raw_messages": raw_messages}
            finally:
                ws.close()

    def fetch_condition_results(
        self,
        *,
        condition_seq: str,
        condition_name: str | None,
        search_type: str = "0",
        stex_tp: str = "K",
    ) -> dict[str, Any]:
        payload = self._fetch_condition_result_via_ws(
            condition_seq=condition_seq,
            condition_name=condition_name,
            search_type=search_type,
            stex_tp=stex_tp,
        )
        items, list_key_used, parse_input_count = self._normalize_condition_results(
            payload,
            condition_seq=condition_seq,
            condition_name=condition_name,
        )
        parsing_error = parse_input_count > 0 and len(items) == 0
        return {
            "source": "kiwoom_ws",
            "api_id": "CNSRREQ",
            "condition_seq": str(condition_seq),
            "condition_name": condition_name,
            "fetched_at": now_kst(),
            "return_code": self._to_str_or_none(payload.get("return_code")),
            "return_msg": self._to_str_or_none(payload.get("return_msg")),
            "item_count": len(items),
            "items": items,
            "parsing_error": parsing_error,
            "debug": {
                "top_level_keys": list(payload.keys())[:20],
                "list_key_used": list_key_used,
                "parse_input_count": parse_input_count,
            },
        }

    def _fetch_condition_result_via_ws(
        self,
        *,
        condition_seq: str,
        condition_name: str | None,
        search_type: str,
        stex_tp: str,
    ) -> dict[str, Any]:
        token = KiwoomAuthClient.get_access_token()
        raw_messages: list[dict[str, Any]] = []
        with self._temporary_proxy_env_disabled(enabled=not self.ws_use_proxy):
            ws = websocket.create_connection(
                self.ws_url,
                timeout=max(self.ws_timeout_seconds, 5),
                header=[f"authorization: Bearer {token}"],
                enable_multithread=True,
                http_proxy_host=None if not self.ws_use_proxy else None,
                http_proxy_port=None if not self.ws_use_proxy else None,
            )
            try:
                ws.send(json.dumps({"trnm": "LOGIN", "token": token}, ensure_ascii=False))
                login_msg = self._wait_for_message(ws, timeout=self.ws_timeout_seconds, stages=raw_messages, stage="login_wait_ack", target_trnm="LOGIN")
                if not isinstance(login_msg, dict) or str(login_msg.get("return_code")) not in {"0", "000000"}:
                    return {"return_code": "1", "return_msg": "LOGIN 실패", "raw_messages": raw_messages}
                ws.send(json.dumps({"trnm": "CNSRLST"}, ensure_ascii=False))
                _ = self._wait_for_message(ws, timeout=self.ws_timeout_seconds, stages=raw_messages, stage="cnsrlst_wait_response", target_trnm="CNSRLST")
                req = {
                    "trnm": "CNSRREQ",
                    "seq": str(condition_seq),
                    "search_type": str(search_type),
                    "stex_tp": str(stex_tp),
                    "cont_yn": "N",
                    "next_key": "",
                }
                if condition_name:
                    req["condition_name"] = condition_name
                ws.send(json.dumps(req, ensure_ascii=False))
                cnsrreq_msg = self._wait_for_message(ws, timeout=self.ws_timeout_seconds, stages=raw_messages, stage="cnsrreq_wait_response", target_trnm="CNSRREQ")
                if isinstance(cnsrreq_msg, dict):
                    cnsrreq_msg["raw_messages"] = raw_messages
                    return cnsrreq_msg
                return {"return_code": "1", "return_msg": "CNSRREQ 응답을 수신하지 못했습니다.", "raw_messages": raw_messages}
            finally:
                ws.close()

    def _wait_for_message(
        self,
        ws: Any,
        *,
        timeout: int,
        stages: list[dict[str, Any]],
        stage: str,
        target_trnm: str,
    ) -> dict[str, Any] | None:
        deadline = time.time() + max(timeout, 3)
        target = target_trnm.upper()
        while time.time() < deadline:
            raw = ws.recv()
            try:
                msg = json.loads(raw)
            except Exception:
                msg = {"raw_text": str(raw)}
            stages.append({"stage": stage, "received": msg})
            if not isinstance(msg, dict):
                continue
            trnm = str(msg.get("trnm") or "").upper()
            if trnm == "PING":
                ws.send(json.dumps(msg, ensure_ascii=False))
                stages.append({"stage": stage, "sent": {"trnm": "PING"}})
                continue
            if trnm == target:
                return msg
        return None

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

    @staticmethod
    def _to_str_or_none(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text if text else None

    @staticmethod
    def _candidate_rows(payload: dict[str, Any]) -> tuple[list[Any], str | None]:
        for key in ("data", "items", "list", "output", "output1", "output2", "conditions", "condition_list", "cond_list", "conds", "search_conditions", "result", "stocks", "조건검색목록"):
            value = payload.get(key)
            if isinstance(value, list):
                return value, key
            if isinstance(value, str) and value.strip():
                parsed = KiwoomRestConditionProvider._parse_condition_string_list(value)
                if parsed:
                    return parsed, key
        for value in payload.values():
            if isinstance(value, dict):
                for nested in value.values():
                    if isinstance(nested, list):
                        return nested, "nested"
                    if isinstance(nested, str) and nested.strip():
                        parsed = KiwoomRestConditionProvider._parse_condition_string_list(nested)
                        if parsed:
                            return parsed, "nested"
        return [], None

    @staticmethod
    def _parse_condition_string_list(value: str) -> list[list[str]]:
        # Some ka10171 responses can be condensed as "1^조건식;2^조건식;..."
        text = value.strip().strip(";")
        if not text:
            return []
        rows: list[list[str]] = []
        for chunk in text.split(";"):
            part = chunk.strip()
            if not part:
                continue
            for sep in ("^", "|", ","):
                if sep in part:
                    seq, name = part.split(sep, 1)
                    seq = seq.strip()
                    name = name.strip()
                    if seq and name:
                        rows.append([seq, name])
                    break
        return rows

    def _normalize_condition_list(self, payload: dict[str, Any]) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        rows, _ = self._candidate_rows(payload)
        for row in rows:
            seq = ""
            name = ""
            if isinstance(row, (list, tuple)) and len(row) >= 2:
                seq = str(row[0]).strip()
                name = str(row[1]).strip()
            elif isinstance(row, dict):
                seq = str(row.get("condition_seq") or row.get("cond_seq") or row.get("seq") or row.get("index") or row.get("condition_no") or row.get("cond_no") or row.get("search_no") or row.get("조건번호") or "").strip()
                name = str(row.get("condition_name") or row.get("cond_name") or row.get("name") or row.get("condition_nm") or row.get("cond_nm") or row.get("search_name") or row.get("조건명") or "").strip()
            if seq and name:
                out.append({"condition_seq": seq, "condition_name": name})
        return out

    def _normalize_condition_results(
        self,
        payload: dict[str, Any],
        *,
        condition_seq: str,
        condition_name: str | None,
    ) -> tuple[list[dict[str, Any]], str | None, int]:
        detected_at = datetime.now().isoformat(timespec="seconds")
        out: list[dict[str, Any]] = []
        rows, list_key_used = self._candidate_rows(payload)
        for row in rows:
            if not isinstance(row, dict):
                continue
            raw_code = str(
                row.get("stock_code")
                or row.get("stk_cd")
                or row.get("code")
                or row.get("item_code")
                or row.get("isu_cd")
                or row.get("jmcode")
                or row.get("shcode")
                or row.get("9001")
                or row.get("종목코드")
                or ""
            ).strip()
            code = "".join(ch for ch in raw_code if ch.isdigit())[-6:].zfill(6) if raw_code else ""
            if len(code) != 6:
                continue
            out.append(
                {
                    "condition_seq": str(condition_seq),
                    "condition_name": condition_name or row.get("condition_name"),
                    "stock_code": code,
                    "stock_code_raw": raw_code or None,
                    "stock_name": row.get("stock_name") or row.get("stk_nm") or row.get("name") or row.get("item_name") or row.get("hname") or row.get("302") or row.get("종목명"),
                    "current_price": self._to_int_or_none(row.get("current_price") or row.get("cur_prc") or row.get("price") or row.get("now_prc") or row.get("close") or row.get("10") or row.get("현재가")),
                    "change_rate": self._to_float_or_none(row.get("change_rate") or row.get("flu_rt") or row.get("chg_rt") or row.get("rate") or row.get("12") or row.get("등락률")),
                    "intraday_change_rate": self._to_float_or_none(row.get("intraday_change_rate") or row.get("open_pric_pre")),
                    "volume": self._to_int_or_none(row.get("volume") or row.get("trde_qty") or row.get("acc_volume") or row.get("now_trde_qty") or row.get("13") or row.get("거래량")),
                    "trading_value": self._to_int_or_none(row.get("trading_value") or row.get("trde_prica") or row.get("acc_trading_value") or row.get("거래대금")),
                    "source_api": "CNSRREQ",
                    "detected_at": detected_at,
                    "raw": row,
                }
            )
        return out, list_key_used, len(rows)

    @staticmethod
    def _to_int_or_none(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(float(str(value).replace(",", "").strip()))
        except Exception:
            return None

    @staticmethod
    def _to_float_or_none(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(str(value).replace(",", "").replace("%", "").strip())
        except Exception:
            return None
