from __future__ import annotations

from typing import Any


class FutureOutcomeService:
    @staticmethod
    def calculate_horizons(
        d0_close: float | None,
        future_rows_asc: list[dict[str, Any]],
        horizons: tuple[int, ...],
        excursion_window: int | None = None,
    ) -> dict[str, float | None]:
        """Calculate close returns and completed-window excursions by actual trading rows."""
        result = {f"d{period}_return": None for period in horizons}
        if excursion_window is not None:
            result[f"mfe_{excursion_window}"] = None
            result[f"mae_{excursion_window}"] = None
        if d0_close in (None, 0):
            return result
        base = float(d0_close)
        for period in horizons:
            row = future_rows_asc[period - 1] if len(future_rows_asc) >= period else None
            close = row.get("close_price") if row else None
            result[f"d{period}_return"] = None if close is None else (float(close) / base - 1) * 100
        if excursion_window is not None and len(future_rows_asc) >= excursion_window:
            window = future_rows_asc[:excursion_window]
            if all(row.get("high_price") is not None and row.get("low_price") is not None for row in window):
                result[f"mfe_{excursion_window}"] = (max(float(row["high_price"]) for row in window) / base - 1) * 100
                result[f"mae_{excursion_window}"] = (min(float(row["low_price"]) for row in window) / base - 1) * 100
        return result

    @staticmethod
    def calculate(d0_close: float | None, future_rows_asc: list[dict[str, Any]]) -> dict[str, float | None]:
        return FutureOutcomeService.calculate_horizons(d0_close, future_rows_asc, (5, 10, 20), 20)
