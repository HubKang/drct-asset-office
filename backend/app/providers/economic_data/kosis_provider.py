from __future__ import annotations

import json
from datetime import date
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from backend.app.core import config


class KosisProvider:
    provider = "KOSIS"

    def __init__(self) -> None:
        self.api_key = config.KOSIS_API_KEY
        self.base_url = config.KOSIS_BASE_URL.rstrip("/")
        self.timeout_seconds = config.KOSIS_TIMEOUT_SECONDS

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def test_mapping(self, mapping: dict[str, Any], *, start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
        params = self._mapping_params(mapping)
        date_to = end_date or date.today().isoformat()
        date_from = start_date or f"{date.today().year - 1}-01-01"
        result = self.fetch_series(params=params, start_date=date_from, end_date=date_to)
        rows = result.get("rows") or []
        valid_rows = [row for row in rows if self._to_float(row.get(params.get("value_field") or "DT")) is not None]
        if result.get("status") != "SUCCESS":
            return result
        if not valid_rows:
            return {"status": "WAITING", "message": "KOSIS returned no numeric rows.", "rows": rows[:20], "count": len(rows)}
        return {"status": "SUCCESS", "message": f"KOSIS mapping returned {len(valid_rows)} numeric rows.", "rows": valid_rows[:50], "count": len(valid_rows)}

    def collect_values(self, indicator_code: str, mapping: dict[str, Any], *, start_date: str, end_date: str) -> list[dict[str, Any]]:
        params = self._mapping_params(mapping)
        result = self.fetch_series(params=params, start_date=start_date, end_date=end_date)
        if result.get("status") != "SUCCESS":
            raise RuntimeError(str(result.get("message") or "KOSIS collection failed"))
        period_field = params.get("period_field") or "PRD_DE"
        value_field = params.get("value_field") or "DT"
        source_unit = params.get("source_unit") or params.get("unit")
        values: list[dict[str, Any]] = []
        previous_value: float | None = None
        monthly_values: dict[str, float] = {}
        frequency = str(params.get("frequency") or params.get("prdSe") or "M").upper()
        for row in sorted(result.get("rows") or [], key=lambda item: str(item.get(period_field) or "")):
            raw_period = str(row.get(period_field) or "")
            value = self._to_float(row.get(value_field))
            value_date = self._value_date(raw_period, frequency)
            if value is None or not value_date:
                continue
            change_value = None if previous_value is None else value - previous_value
            change_pct = None if previous_value in (None, 0) else (value - previous_value) / previous_value * 100
            period_key = raw_period[:6]
            yoy_pct = None
            if frequency == "M" and len(period_key) >= 6:
                prior = monthly_values.get(f"{int(period_key[:4]) - 1}{period_key[4:6]}")
                yoy_pct = None if prior in (None, 0) else (value - prior) / prior * 100
            values.append(
                {
                    "indicator_code": indicator_code,
                    "value_date": value_date,
                    "period_label": value_date[:7],
                    "value": value,
                    "change_value": change_value,
                    "change_pct": change_pct,
                    "mom_pct": change_pct if frequency == "M" else None,
                    "yoy_pct": yoy_pct,
                    "source_provider": self.provider,
                    "source_unit": source_unit,
                    "is_preliminary": 0,
                    "release_date": None,
                    "raw_payload_json": None,
                }
            )
            if frequency == "M" and len(period_key) >= 6:
                monthly_values[period_key] = value
            previous_value = value
        return values

    def fetch_series(self, *, params: dict[str, Any], start_date: str, end_date: str) -> dict[str, Any]:
        if not self.is_configured():
            return {"status": "WAITING", "message": "KOSIS_API_KEY is not configured.", "rows": [], "count": 0}
        request_params = dict(params)
        request_params.pop("source_unit", None)
        request_params.pop("unit", None)
        request_params.pop("frequency", None)
        request_params.pop("period_field", None)
        request_params.pop("value_field", None)
        request_params.setdefault("method", "getList")
        request_params.setdefault("format", "json")
        request_params.setdefault("jsonVD", "Y")
        request_params["apiKey"] = self.api_key
        request_params["startPrdDe"] = self._period(start_date, str(params.get("frequency") or params.get("prdSe") or "M"))
        request_params["endPrdDe"] = self._period(end_date, str(params.get("frequency") or params.get("prdSe") or "M"))
        endpoint = str(params.get("endpoint") or "Param/statisticsParameterData.do").lstrip("/")
        request_params.pop("endpoint", None)
        url = f"{self.base_url}/{endpoint}?{urlencode(request_params)}"
        request = Request(url, headers={"Accept": "application/json", "User-Agent": "drct-asset-office/1.0"})
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8-sig"))
        except HTTPError as exc:
            return {"status": "ERROR", "message": f"KOSIS HTTP request failed: {exc.code}", "rows": [], "count": 0}
        except URLError as exc:
            return {"status": "ERROR", "message": f"KOSIS network error: {exc.reason}", "rows": [], "count": 0}
        except json.JSONDecodeError:
            return {"status": "ERROR", "message": "KOSIS returned invalid JSON.", "rows": [], "count": 0}
        rows = payload if isinstance(payload, list) else payload.get("data", []) if isinstance(payload, dict) else []
        if isinstance(rows, dict):
            rows = [rows]
        if not isinstance(rows, list):
            rows = []
        return {"status": "SUCCESS", "message": "OK", "rows": [row for row in rows if isinstance(row, dict)], "count": len(rows)}

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

    @staticmethod
    def _period(value: str, frequency: str) -> str:
        compact = str(value or "").replace("-", "")
        return compact[:6] if str(frequency).upper().startswith("M") else compact[:8]

    @staticmethod
    def _value_date(value: str, frequency: str) -> str | None:
        raw = str(value or "").strip()
        if not raw:
            return None
        if str(frequency).upper().startswith("M") and len(raw) >= 6:
            return f"{raw[:4]}-{raw[4:6]}-01"
        if len(raw) >= 8:
            return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
        if len(raw) >= 6:
            return f"{raw[:4]}-{raw[4:6]}-01"
        return None

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(str(value).replace(",", "").strip())
        except ValueError:
            return None
