from __future__ import annotations

import re
from typing import Any


def normalize_kiwoom_sign_number(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip().replace(",", "")
    return s


def clean_number(value: Any) -> int | None:
    s = normalize_kiwoom_sign_number(value)
    if not s:
        return None
    sign = -1 if s.startswith("-") else 1
    s = s.lstrip("+-")
    if not s.isdigit():
        return None
    n = int(s)
    return sign * n


def clean_rate(value: Any) -> float | None:
    s = normalize_kiwoom_sign_number(value)
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


def clean_rate_from_milli_percent(value: Any) -> float | None:
    rate = clean_rate(value)
    if rate is None:
        return None
    return rate / 1000.0


def clean_abs_number(value: Any) -> int | None:
    n = clean_number(value)
    if n is None:
        return None
    return abs(n)


def _abs_price(value: Any) -> int | None:
    n = clean_number(value)
    if n is None:
        return None
    return abs(n)


def normalize_stock_code(value: str | None) -> str:
    if value is None:
        return ""
    raw = str(value).strip()
    if not raw:
        return ""
    core = raw.split("_", 1)[0].strip()
    if len(core) == 7 and core.upper().startswith("A") and core[1:].isdigit():
        core = core[1:]
    if core.isdigit() and len(core) == 6:
        return core
    m = re.search(r"(\d{6})", core)
    if m:
        return m.group(1)
    return ""


def map_intraday_change_item(raw_item: dict) -> dict:
    stock_code_raw = (raw_item.get("stk_cd") or "").strip()
    return {
        "stock_code": normalize_stock_code(stock_code_raw),
        "stock_code_raw": stock_code_raw,
        "stock_name": (raw_item.get("stk_nm") or "").strip(),
        "current_price": _abs_price(raw_item.get("cur_prc")),
        "open_price": _abs_price(raw_item.get("open_pric")),
        "high_price": _abs_price(raw_item.get("high_pric")),
        "low_price": _abs_price(raw_item.get("low_pric")),
        "volume": abs(clean_number(raw_item.get("now_trde_qty")) or 0),
        "trading_value": None,
        "intraday_change_rate": clean_rate(raw_item.get("open_pric_pre")),
        "day_change_rate": clean_rate(raw_item.get("flu_rt")),
        "strength": clean_rate(raw_item.get("cntr_str")),
        "source_api": "ka10028",
        "source_rank": clean_number(raw_item.get("rank_no")),
    }


def map_to_market_event_payload(items: list[dict]) -> dict:
    mapped = [map_intraday_change_item(x) for x in items]
    return {
        "source": "kiwoom_rest_ka10028",
        "count": len(mapped),
        "items": mapped,
    }
