from __future__ import annotations

import re


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
