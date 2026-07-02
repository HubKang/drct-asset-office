from __future__ import annotations

import json
import time
from datetime import date, timedelta
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

_TABLE_LIST_CACHE: dict[tuple[str | None, int, int, str], tuple[float, dict[str, Any]]] = {}
_TABLE_LIST_CACHE_TTL_SECONDS = 600

from backend.app.core.config import (
    BOK_ECOS_API_KEY,
    BOK_ECOS_BASE_URL,
    BOK_ECOS_TIMEOUT_SECONDS,
)


class BokEcosProvider:
    provider = "BOK_ECOS"

    def __init__(self) -> None:
        self.api_key = BOK_ECOS_API_KEY.strip()
        self.base_url = BOK_ECOS_BASE_URL.rstrip("/")
        self.timeout_seconds = BOK_ECOS_TIMEOUT_SECONDS

    def is_configured(self) -> bool:
        return bool(self.api_key)


    def table_list(
        self,
        *,
        parent_stat_code: str | None = None,
        start_index: int = 1,
        end_index: int = 100,
        language: str = "kr",
    ) -> dict[str, Any]:
        if not self.is_configured():
            return self._missing_key_result()
        cache_key = (parent_stat_code.strip() if parent_stat_code else None, start_index, end_index, language or "kr")
        cached = _TABLE_LIST_CACHE.get(cache_key)
        now = time.monotonic()
        if cached and now - cached[0] < _TABLE_LIST_CACHE_TTL_SECONDS:
            return cached[1]

        path = [
            "StatisticTableList",
            self.api_key,
            "json",
            language or "kr",
            str(start_index),
            str(end_index),
        ]
        if parent_stat_code:
            path.append(parent_stat_code.strip())
        payload = self._request(path)
        result = self._extract_table(payload, "StatisticTableList")
        rows = [self._normalize_table_row(row) for row in result.get("rows") or []]
        normalized = {**result, "rows": rows, "total_count": int(result.get("list_total_count") or len(rows) or 0)}
        if normalized.get("status") == "SUCCESS":
            _TABLE_LIST_CACHE[cache_key] = (now, normalized)
        return normalized

    def search_tables_by_keyword(
        self,
        *,
        keyword: str,
        parent_stat_code: str | None = None,
        max_depth: int = 2,
        cycle: str | None = None,
        only_searchable: bool = False,
    ) -> dict[str, Any]:
        normalized_keyword = (keyword or "").strip().lower()
        if not normalized_keyword:
            return {"status": "ERROR", "message": "keyword is required", "items": [], "searched_count": 0}

        page_size = 1000
        first = self.table_list(parent_stat_code=parent_stat_code, start_index=1, end_index=page_size)
        if first.get("status") != "SUCCESS":
            return {"status": first.get("status") or "ERROR", "message": first.get("message") or "", "items": [], "searched_count": 0}

        rows = list(first.get("rows") or [])
        total_count = int(first.get("total_count") or first.get("list_total_count") or len(rows) or 0)
        for start_index in range(page_size + 1, total_count + 1, page_size):
            end_index = min(start_index + page_size - 1, total_count)
            page = self.table_list(parent_stat_code=parent_stat_code, start_index=start_index, end_index=end_index)
            if page.get("status") != "SUCCESS":
                break
            rows.extend(page.get("rows") or [])

        matched: list[dict[str, Any]] = []
        allowed_parent: set[str] | None = None
        if parent_stat_code:
            allowed_parent = {parent_stat_code.strip()}
            if max_depth > 0:
                current = {parent_stat_code.strip()}
                for _ in range(max_depth):
                    children = {str(row.get("stat_code") or "") for row in rows if str(row.get("p_stat_code") or "") in current}
                    children.discard("")
                    allowed_parent.update(children)
                    current = children

        for row in rows:
            if allowed_parent is not None and str(row.get("p_stat_code") or "") not in allowed_parent and str(row.get("stat_code") or "") not in allowed_parent:
                continue
            row_cycle = str(row.get("cycle") or "").upper()
            row_searchable = str(row.get("srch_yn") or "").upper() == "Y"
            stat_name = str(row.get("stat_name") or "")
            if normalized_keyword not in stat_name.lower():
                continue
            if cycle and row_cycle != cycle.upper():
                continue
            if only_searchable and not row_searchable:
                continue
            matched.append(row)

        return {
            "status": "SUCCESS",
            "message": f"searched {len(rows)} ECOS statistic tables",
            "items": matched,
            "searched_count": len(rows),
        }

    def item_list(self, stat_code: str, *, start_index: int = 1, end_index: int = 100) -> dict[str, Any]:
        if not self.is_configured():
            return self._missing_key_result()
        path = ["StatisticItemList", self.api_key, "json", "kr", str(start_index), str(end_index), stat_code.strip()]
        payload = self._request(path)
        return self._extract_table(payload, "StatisticItemList")

    def statistic_search(
        self,
        *,
        stat_code: str,
        cycle: str,
        start_date: str,
        end_date: str,
        item_code1: str | None = None,
        item_code2: str | None = None,
        item_code3: str | None = None,
        item_code4: str | None = None,
        start_index: int = 1,
        end_index: int = 1000,
    ) -> dict[str, Any]:
        if not self.is_configured():
            return self._missing_key_result()
        normalized_cycle = (cycle or "D").strip().upper()
        path = [
            "StatisticSearch",
            self.api_key,
            "json",
            "kr",
            str(start_index),
            str(end_index),
            stat_code.strip(),
            normalized_cycle,
            self._format_period(start_date, normalized_cycle),
            self._format_period(end_date, normalized_cycle),
        ]
        for code in (item_code1, item_code2, item_code3, item_code4):
            if code:
                path.append(str(code).strip())
        payload = self._request(path)
        return self._extract_table(payload, "StatisticSearch")

    def test_mapping(self, mapping: dict[str, Any], *, start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
        params = self._mapping_params(mapping)
        date_to = end_date or date.today().isoformat()
        date_from = start_date or (date.today() - timedelta(days=370)).isoformat()
        result = self.statistic_search(
            stat_code=params.get("stat_code") or mapping.get("api_id") or "",
            cycle=params.get("cycle") or "D",
            start_date=date_from,
            end_date=date_to,
            item_code1=params.get("item_code1") or mapping.get("provider_symbol"),
            item_code2=params.get("item_code2"),
            item_code3=params.get("item_code3"),
            item_code4=params.get("item_code4"),
            start_index=int(params.get("start_index") or 1),
            end_index=int(params.get("end_index") or 100),
        )
        rows = result.get("rows") or []
        valid_rows = [row for row in rows if self._to_float(row.get("DATA_VALUE")) is not None]
        if result.get("status") != "SUCCESS":
            return result
        if not valid_rows:
            return {"status": "WAITING", "message": "ECOS returned no numeric DATA_VALUE rows.", "rows": rows, "list_total_count": result.get("list_total_count", 0)}
        return {
            "status": "SUCCESS",
            "message": f"ECOS mapping returned {len(valid_rows)} numeric rows.",
            "rows": valid_rows,
            "list_total_count": result.get("list_total_count", len(rows)),
        }

    def collect_values(self, indicator_code: str, mapping: dict[str, Any], *, start_date: str, end_date: str) -> list[dict[str, Any]]:
        params = self._mapping_params(mapping)
        cycle = params.get("cycle") or "D"
        result = self.statistic_search(
            stat_code=params.get("stat_code") or mapping.get("api_id") or "",
            cycle=cycle,
            start_date=start_date,
            end_date=end_date,
            item_code1=params.get("item_code1") or mapping.get("provider_symbol"),
            item_code2=params.get("item_code2"),
            item_code3=params.get("item_code3"),
            item_code4=params.get("item_code4"),
            start_index=int(params.get("start_index") or 1),
            end_index=int(params.get("end_index") or 1000),
        )
        if result.get("status") != "SUCCESS":
            raise RuntimeError(str(result.get("message") or "ECOS collection failed"))
        values: list[dict[str, Any]] = []
        previous_value: float | None = None
        monthly_values: dict[str, float] = {}
        normalized_cycle = str(cycle).upper()
        for row in sorted(result.get("rows") or [], key=lambda item: str(item.get("TIME") or "")):
            raw_time = str(row.get("TIME") or "")
            value = self._to_float(row.get("DATA_VALUE"))
            value_date = self._value_date(raw_time, cycle)
            if value is None or not value_date:
                continue
            change_value = None if previous_value is None else value - previous_value
            change_pct = None if previous_value in (None, 0) else (value - previous_value) / previous_value * 100
            period_key = raw_time[:6]
            yoy_pct = None
            if normalized_cycle == "M" and len(period_key) == 6:
                prior_key = f"{int(period_key[:4]) - 1}{period_key[4:6]}"
                prior_value = monthly_values.get(prior_key)
                yoy_pct = None if prior_value in (None, 0) else (value - prior_value) / prior_value * 100
            values.append(
                {
                    "indicator_code": indicator_code,
                    "value_date": value_date,
                    "period_label": self._period_label(raw_time, cycle) or str(row.get("TIME") or value_date),
                    "value": value,
                    "change_value": change_value,
                    "change_pct": change_pct,
                    "mom_pct": change_pct if normalized_cycle == "M" else None,
                    "yoy_pct": yoy_pct,
                    "source_provider": self.provider,
                    "source_unit": row.get("UNIT_NAME") or params.get("source_unit"),
                    "is_preliminary": 0,
                    "release_date": None,
                    "raw_payload_json": json.dumps(self._sanitize_row(row), ensure_ascii=False),
                }
            )
            if normalized_cycle == "M" and len(period_key) == 6:
                monthly_values[period_key] = value
            previous_value = value
        return values
    def _request(self, path_parts: list[str]) -> dict[str, Any]:
        url = "/".join([self.base_url] + [quote(part, safe="") for part in path_parts])
        request = Request(url, headers={"Accept": "application/json", "User-Agent": "drct-asset-office/1.0"})
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8-sig")
                return json.loads(raw)
        except HTTPError as exc:
            return {"RESULT": {"CODE": f"HTTP_{exc.code}", "MESSAGE": "BOK ECOS HTTP request failed."}}
        except URLError as exc:
            return {"RESULT": {"CODE": "NETWORK_ERROR", "MESSAGE": str(exc.reason)}}
        except json.JSONDecodeError:
            return {"RESULT": {"CODE": "INVALID_JSON", "MESSAGE": "BOK ECOS returned invalid JSON."}}

    def _extract_table(self, payload: dict[str, Any], table_name: str) -> dict[str, Any]:
        result = payload.get("RESULT")
        if isinstance(result, dict):
            return {"status": "ERROR", "message": str(result.get("MESSAGE") or result.get("CODE") or "BOK ECOS error"), "rows": [], "list_total_count": 0}
        table = payload.get(table_name)
        if not isinstance(table, dict):
            return {"status": "ERROR", "message": f"BOK ECOS response does not include {table_name}.", "rows": [], "list_total_count": 0}
        rows = table.get("row") or []
        if isinstance(rows, dict):
            rows = [rows]
        return {
            "status": "SUCCESS",
            "message": "OK",
            "rows": rows if isinstance(rows, list) else [],
            "list_total_count": int(table.get("list_total_count") or len(rows) or 0),
        }


    def _normalize_table_row(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "p_stat_code": row.get("P_STAT_CODE"),
            "stat_code": row.get("STAT_CODE"),
            "stat_name": row.get("STAT_NAME"),
            "cycle": row.get("CYCLE"),
            "srch_yn": row.get("SRCH_YN"),
            "org_name": row.get("ORG_NAME"),
        }

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

    def _missing_key_result(self) -> dict[str, Any]:
        return {"status": "WAITING", "message": "BOK_ECOS_API_KEY is not configured.", "rows": [], "list_total_count": 0}

    def _format_period(self, value: str, cycle: str) -> str:
        compact = str(value or "").replace("-", "").replace(".", "")
        if cycle == "M":
            return compact[:6]
        return compact[:8]

    def _period_label(self, value: Any, cycle: str) -> str | None:
        raw = str(value or "").strip()
        if str(cycle).upper() == "M" and len(raw) >= 6:
            return f"{raw[:4]}-{raw[4:6]}"
        return raw or None

    def _value_date(self, value: Any, cycle: str) -> str | None:
        raw = str(value or "").strip()
        if not raw:
            return None
        if cycle == "M" and len(raw) >= 6:
            return f"{raw[:4]}-{raw[4:6]}-01"
        if len(raw) >= 8:
            return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
        if len(raw) >= 6:
            return f"{raw[:4]}-{raw[4:6]}-01"
        return raw

    def _to_float(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(str(value).replace(",", "").strip())
        except ValueError:
            return None

    def _sanitize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        blocked = {"API_KEY", "AUTH_KEY", "KEY"}
        return {key: value for key, value in row.items() if str(key).upper() not in blocked}