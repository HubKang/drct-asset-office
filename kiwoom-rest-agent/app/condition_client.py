from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import Settings
from .logger import get_logger
from .mapper import clean_abs_number, clean_number, clean_rate, clean_rate_from_milli_percent, normalize_stock_code
from .ws_client import KiwoomWsClient


class ConditionClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = get_logger(__name__)
        self.ws = KiwoomWsClient(settings)

    def get_condition_list(self, token: str, header_mode: str = "auth-only", login_mode: str = "message-token") -> dict[str, Any]:
        return self.ws.request_condition_list(token=token, header_mode=header_mode, login_mode=login_mode)

    def get_condition_once(
        self,
        token: str,
        seq: str,
        condition_name: str | None = None,
        header_mode: str = "auth-only",
        login_mode: str = "message-token",
        search_type: str = "0",
        stex_tp: str = "K",
    ) -> dict[str, Any]:
        return self.ws.request_condition_once(
            token=token,
            condition_seq=seq,
            condition_name=condition_name,
            header_mode=header_mode,
            login_mode=login_mode,
            search_type=search_type,
            stex_tp=stex_tp,
        )

    def normalize_condition_list(self, raw: dict[str, Any]) -> list[dict[str, Any]]:
        base = raw.get("response") if isinstance(raw, dict) else None
        if not isinstance(base, dict):
            base = raw if isinstance(raw, dict) else {}

        candidates: list[Any] = []
        data_value = base.get("data") if isinstance(base, dict) else None
        if isinstance(data_value, list):
            candidates = data_value

        if not candidates:
            for key in ["items", "list", "output", "conditions"]:
                v = base.get(key) if isinstance(base, dict) else None
                if isinstance(v, list):
                    candidates = v
                    break

        out: list[dict[str, Any]] = []
        for row in candidates:
            seq = ""
            name = ""
            if isinstance(row, (list, tuple)) and len(row) >= 2:
                seq = str(row[0]).strip()
                name = str(row[1]).strip()
            elif isinstance(row, dict):
                seq = str(row.get("condition_seq") or row.get("seq") or row.get("index") or "").strip()
                name = str(row.get("condition_name") or row.get("name") or row.get("condition_nm") or "").strip()
            if seq and name:
                out.append({"condition_seq": seq, "condition_name": name, "source": "kiwoom_rest"})
        return out

    def normalize_condition_result(self, raw: dict[str, Any], condition_seq: str, condition_name: str | None = None) -> list[dict[str, Any]]:
        response = raw.get("response", {}) if isinstance(raw, dict) else {}
        candidates: list[Any] = []
        for key in ["items", "list", "output", "data", "stocks", "result"]:
            v = response.get(key) if isinstance(response, dict) else None
            if isinstance(v, list):
                candidates = v
                break

        detected_at = datetime.now().isoformat(timespec="seconds")
        out: list[dict[str, Any]] = []
        for row in candidates:
            if isinstance(row, dict):
                stock_code_raw = str(
                    row.get("stock_code")
                    or row.get("stk_cd")
                    or row.get("code")
                    or row.get("9001")
                    or row.get("item_code")
                    or row.get("symbol")
                    or ""
                ).strip()
                stock_name = row.get("stock_name") or row.get("stk_nm") or row.get("name") or row.get("item_name") or row.get("302")
                current_price = row.get("current_price") or row.get("cur_prc") or row.get("price") or row.get("10")
                change_rate_raw = row.get("change_rate") or row.get("flu_rt") or row.get("12")
                intraday_change_rate = row.get("intraday_change_rate") or row.get("open_pric_pre")
                volume = row.get("volume") or row.get("now_trde_qty") or row.get("13")
                trading_value = row.get("trading_value") or row.get("trde_prica")
                raw_json = row
            elif isinstance(row, (list, tuple)):
                stock_code_raw = str(row[0]).strip() if len(row) > 0 else ""
                stock_name = str(row[1]).strip() if len(row) > 1 else None
                current_price = row[2] if len(row) > 2 else None
                change_rate_raw = row[3] if len(row) > 3 else None
                intraday_change_rate = row[4] if len(row) > 4 else None
                volume = row[5] if len(row) > 5 else None
                trading_value = row[6] if len(row) > 6 else None
                raw_json = {"row": list(row)}
            else:
                continue

            stock_code = normalize_stock_code(stock_code_raw)
            if len(stock_code) != 6:
                continue
            out.append(
                {
                    "condition_seq": condition_seq,
                    "condition_name": condition_name or (row.get("condition_name") if isinstance(row, dict) else None),
                    "stock_code": stock_code,
                    "stock_code_raw": stock_code_raw,
                    "stock_name": stock_name,
                    "current_price": clean_abs_number(current_price),
                    "change_rate": clean_rate_from_milli_percent(change_rate_raw),
                    "change_rate_raw": str(change_rate_raw) if change_rate_raw is not None else None,
                    "intraday_change_rate": clean_rate(intraday_change_rate),
                    "volume": abs(clean_number(volume) or 0),
                    "trading_value": clean_number(trading_value),
                    "source": "kiwoom_rest",
                    "source_api": "ka10172",
                    "detected_at": detected_at,
                    "raw": raw_json,
                    "raw_json": raw_json,
                }
            )
        return out

    @staticmethod
    def save_json(path: Path, data: dict | list) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
