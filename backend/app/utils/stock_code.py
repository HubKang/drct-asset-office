from __future__ import annotations

import re


def normalize_stock_code(value: str | None) -> str:
    if value is None:
        return ""
    raw = str(value).strip()
    if not raw:
        return ""

    core = raw.split("_", 1)[0].strip().upper()
    if len(core) == 7 and core.startswith("A") and core[1:].isalnum():
        core = core[1:]

    # Current KRX short codes may contain letters. Preserve the canonical
    # six-character code instead of collapsing it to a legacy digits-only one.
    if len(core) == 6 and core.isalnum():
        return core

    m = re.search(r"(\d{6})", core)
    if m:
        return m.group(1)

    return ""
