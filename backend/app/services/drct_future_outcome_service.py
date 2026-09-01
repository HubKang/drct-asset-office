from __future__ import annotations

from typing import Any


class FutureOutcomeService:
    @staticmethod
    def calculate(d0_close: float | None, future_rows_asc: list[dict[str, Any]]) -> dict[str, float | None]:
        if d0_close in (None, 0):
            return {"d5_return": None, "d10_return": None, "d20_return": None, "mfe_20": None, "mae_20": None}
        result: dict[str, float | None] = {}
        for period in (5, 10, 20):
            row = future_rows_asc[period - 1] if len(future_rows_asc) >= period else None
            close = row.get("close_price") if row else None
            result[f"d{period}_return"] = None if close is None else (float(close) / float(d0_close) - 1) * 100
        if len(future_rows_asc) < 20 or any(row.get("high_price") is None or row.get("low_price") is None for row in future_rows_asc[:20]):
            result["mfe_20"] = None
            result["mae_20"] = None
        else:
            result["mfe_20"] = (max(float(row["high_price"]) for row in future_rows_asc[:20]) / float(d0_close) - 1) * 100
            result["mae_20"] = (min(float(row["low_price"]) for row in future_rows_asc[:20]) / float(d0_close) - 1) * 100
        return result
