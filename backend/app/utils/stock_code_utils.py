from __future__ import annotations


def normalize_kr_stock_code(code: str | None) -> str:
    if code is None:
        return ""
    value = str(code).strip().upper()
    if len(value) == 7 and value.startswith("A") and value[1:].isdigit():
        return value[1:]
    if len(value) == 6 and value.isdigit():
        return value
    return value


def is_valid_kr_stock_code(code: str | None) -> bool:
    value = normalize_kr_stock_code(code)
    return len(value) == 6 and value.isdigit()
