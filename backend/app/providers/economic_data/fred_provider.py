from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from backend.app.core.config import FRED_API_KEY, FRED_BASE_URL, FRED_TIMEOUT_SECONDS


class FredProvider:
    provider = "FRED"

    def __init__(self) -> None:
        self.api_key = FRED_API_KEY.strip()
        self.base_url = FRED_BASE_URL.rstrip("/")
        self.timeout_seconds = FRED_TIMEOUT_SECONDS

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def fetch_series_observations(self, *, series_id: str, start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
        if not self.is_configured():
            return {"status": "WAITING", "message": "FRED_API_KEY is not configured.", "rows": [], "count": 0}
        normalized_series = (series_id or "").strip().upper()
        if not normalized_series:
            return {"status": "ERROR", "message": "series_id is required.", "rows": [], "count": 0}
        params = {
            "api_key": self.api_key,
            "series_id": normalized_series,
            "file_type": "json",
        }
        if start_date:
            params["observation_start"] = str(start_date)[:10]
        if end_date:
            params["observation_end"] = str(end_date)[:10]
        url = f"{self.base_url}/series/observations?{urlencode(params)}"
        request = Request(url, headers={"Accept": "application/json", "User-Agent": "drct-asset-office/1.0"})
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return {"status": "ERROR", "message": f"FRED HTTP request failed: {exc.code}", "rows": [], "count": 0}
        except URLError as exc:
            return {"status": "ERROR", "message": f"FRED network error: {exc.reason}", "rows": [], "count": 0}
        except json.JSONDecodeError:
            return {"status": "ERROR", "message": "FRED returned invalid JSON.", "rows": [], "count": 0}
        observations = payload.get("observations") or []
        if not isinstance(observations, list):
            observations = []
        return {"status": "SUCCESS", "message": "OK", "rows": [self._sanitize_row(row) for row in observations if isinstance(row, dict)], "count": len(observations)}

    def test_mapping(self, mapping: dict[str, Any], *, start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
        params = self._mapping_params(mapping)
        series_id = params.get("series_id") or mapping.get("provider_symbol") or mapping.get("api_id") or ""
        date_to = end_date or date.today().isoformat()
        date_from = start_date or (date.today() - timedelta(days=180)).isoformat()
        result = self.fetch_series_observations(series_id=str(series_id), start_date=date_from, end_date=date_to)
        rows = result.get("rows") or []
        valid_rows = [row for row in rows if self._to_float(row.get("value")) is not None]
        if result.get("status") != "SUCCESS":
            return result
        if not valid_rows:
            return {"status": "WAITING", "message": "FRED returned no numeric observation rows.", "rows": rows[:20], "count": len(rows)}
        return {"status": "SUCCESS", "message": f"FRED mapping returned {len(valid_rows)} numeric rows.", "rows": valid_rows, "count": len(valid_rows)}

    def collect_values(self, indicator_code: str, mapping: dict[str, Any], *, start_date: str, end_date: str) -> list[dict[str, Any]]:
        params = self._mapping_params(mapping)
        series_id = params.get("series_id") or mapping.get("provider_symbol") or mapping.get("api_id") or ""
        scale = self._to_float(params.get("scale")) or 1.0
        source_unit = params.get("source_unit") or mapping.get("unit")
        result = self.fetch_series_observations(series_id=str(series_id), start_date=start_date, end_date=end_date)
        if result.get("status") != "SUCCESS":
            raise RuntimeError(str(result.get("message") or "FRED collection failed"))
        values: list[dict[str, Any]] = []
        previous_value: float | None = None
        monthly_values: list[float] = []
        is_monthly_price_index = str(indicator_code or "").upper() in {"US_CPI", "US_CORE_PCE"}
        for row in sorted(result.get("rows") or [], key=lambda item: str(item.get("date") or "")):
            value_date = str(row.get("date") or "")[:10]
            value = self._to_float(row.get("value"))
            if not value_date or value is None:
                continue
            value *= scale
            change_value = None if previous_value is None else value - previous_value
            change_pct = None if previous_value in (None, 0) else (value - previous_value) / previous_value * 100
            mom_pct = change_pct if is_monthly_price_index else None
            yoy_base = monthly_values[-12] if is_monthly_price_index and len(monthly_values) >= 12 else None
            yoy_pct = None if yoy_base in (None, 0) else (value - yoy_base) / yoy_base * 100
            values.append(
                {
                    "indicator_code": indicator_code,
                    "value_date": value_date,
                    "period_label": value_date[:7] if is_monthly_price_index else None,
                    "value": value,
                    "change_value": change_value,
                    "change_pct": change_pct,
                    "mom_pct": mom_pct,
                    "yoy_pct": yoy_pct,
                    "source_provider": self.provider,
                    "source_unit": source_unit,
                    "is_preliminary": 0,
                    "release_date": None,
                    "raw_payload_json": None,
                }
            )
            previous_value = value
            if is_monthly_price_index:
                monthly_values.append(value)
        return values

    def _mapping_params(self, mapping: dict[str, Any]) -> dict[str, Any]:
        raw = mapping.get("request_params_json")
        if isinstance(raw, dict):
            return raw
        if not raw:
            return {}
        try:
            parsed = json.loads(str(raw))
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _to_float(self, value: Any) -> float | None:
        if value is None:
            return None
        text = str(value).replace(",", "").strip()
        if not text or text == ".":
            return None
        try:
            return float(text)
        except ValueError:
            return None

    def _sanitize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        blocked = {"API_KEY", "AUTH_KEY", "KEY"}
        return {key: value for key, value in row.items() if str(key).upper() not in blocked}
