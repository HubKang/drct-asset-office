from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.providers.economic_data.bok_ecos_provider import BokEcosProvider
from backend.app.providers.economic_data.fred_provider import FredProvider
from backend.app.providers.economic_data.kosis_provider import KosisProvider

ECOS_DISCOVERY_TARGETS: dict[str, dict[str, Any]] = {
    "USD_KRW": {
        "keywords": ["\ud658\uc728", "\ub2ec\ub7ec", "\ubbf8\ub2ec\ub7ec", "\ub9e4\ub9e4\uae30\uc900\uc728"],
        "preferred_cycle": "D",
        "terms": ["\ub2ec\ub7ec", "\ubbf8\ub2ec\ub7ec", "\ub300\ubbf8"],
        "item_terms": ["\ub2ec\ub7ec", "\ubbf8\uad6d\ub2ec\ub7ec", "\ubbf8\ub2ec\ub7ec", "\ub300\ubbf8\ub2ec\ub7ec", "\ub9e4\ub9e4\uae30\uc900\uc728"],
        "negative_terms": ["\uc1a1\uae08", "\ub9e4\uc785", "\ub9e4\ub3c4"],
        "required_all": ["\uc6d0/", "\ub2ec\ub7ec"],
    },
    "JPY_KRW": {
        "keywords": ["\ud658\uc728", "\uc5d4", "\uc77c\ubcf8\uc5d4"],
        "preferred_cycle": "D",
        "terms": ["\uc5d4", "\uc77c\ubcf8"],
        "item_terms": ["\uc5d4", "\uc77c\ubcf8\uc5d4", "100\uc5d4", "\ub9e4\ub9e4\uae30\uc900\uc728"],
        "negative_terms": ["\uc1a1\uae08", "\ub9e4\uc785", "\ub9e4\ub3c4"],
        "required_all": ["\uc6d0/", "\uc5d4"],
    },
    "CNY_KRW": {
        "keywords": ["\ud658\uc728", "\uc704\uc548", "\uc911\uad6d\uc704\uc548"],
        "preferred_cycle": "D",
        "terms": ["\uc704\uc548", "\uc911\uad6d"],
        "item_terms": ["\uc704\uc548", "\uc911\uad6d\uc704\uc548", "\ub300\uc704\uc548", "\ub9e4\ub9e4\uae30\uc900\uc728"],
        "negative_terms": ["\uc1a1\uae08", "\ub9e4\uc785", "\ub9e4\ub3c4"],
        "required_all": ["\uc6d0/", "\uc704\uc548"],
    },
    "BASE_RATE": {
        "keywords": ["\uae30\uc900\uae08\ub9ac", "\ud55c\uad6d\uc740\ud589 \uae30\uc900\uae08\ub9ac"],
        "preferred_cycle": "M",
        "terms": ["\uae30\uc900\uae08\ub9ac", "\ud55c\uad6d\uc740\ud589"],
        "item_terms": ["\uae30\uc900\uae08\ub9ac", "\uc815\ucc45\uae08\ub9ac", "\ud55c\uad6d\uc740\ud589"],
        "negative_terms": [],
        "required_all": ["\uae30\uc900\uae08\ub9ac"],
    },
    "CALL_RATE": {
        "keywords": ["\ucf5c\uae08\ub9ac", "\uc2dc\uc7a5\uae08\ub9ac", "\uae08\ub9ac"],
        "preferred_cycle": "D",
        "terms": ["\ucf5c", "\ucf5c\uae08\ub9ac"],
        "item_terms": ["\ucf5c\uae08\ub9ac", "\ucf5c", "\uc775\uc77c\ubb3c", "\ubb34\ub2f4\ubcf4"],
        "negative_terms": ["\ud68c\uc0ac\ucc44", "CD", "\ud1b5\uc548\uc99d\uad8c"],
        "required_all": ["\ucf5c\uae08\ub9ac"],
    },
    "KTB_3Y": {
        "keywords": ["\uad6d\uace0\ucc44", "\uad6d\uace0\ucc44 3\ub144", "\uc2dc\uc7a5\uae08\ub9ac"],
        "preferred_cycle": "D",
        "terms": ["\uad6d\uace0\ucc44", "3\ub144"],
        "item_terms": ["\uad6d\uace0\ucc44", "\uad6d\uace0\ucc44\uad8c", "3\ub144"],
        "negative_terms": ["\ud68c\uc0ac\ucc44", "CD", "\ud1b5\uc548\uc99d\uad8c", "10\ub144"],
        "required_all": ["\uad6d\uace0\ucc44", "3\ub144"],
    },
    "KTB_10Y": {
        "keywords": ["\uad6d\uace0\ucc44", "\uad6d\uace0\ucc44 10\ub144", "\uc2dc\uc7a5\uae08\ub9ac"],
        "preferred_cycle": "D",
        "terms": ["\uad6d\uace0\ucc44", "10\ub144"],
        "item_terms": ["\uad6d\uace0\ucc44", "\uad6d\uace0\ucc44\uad8c", "10\ub144"],
        "negative_terms": ["\ud68c\uc0ac\ucc44", "CD", "\ud1b5\uc548\uc99d\uad8c", "3\ub144"],
        "required_all": ["\uad6d\uace0\ucc44", "10\ub144"],
    },
    "CPI": {
        "keywords": ["\uc18c\ube44\uc790\ubb3c\uac00\uc9c0\uc218", "\uc18c\ube44\uc790\ubb3c\uac00", "\ubb3c\uac00\uc9c0\uc218", "CPI"],
        "preferred_cycle": "M",
        "terms": ["\uc18c\ube44\uc790\ubb3c\uac00", "\uc18c\ube44\uc790\ubb3c\uac00\uc9c0\uc218"],
        "item_terms": ["\ucd1d\uc9c0\uc218", "\uc804\uad6d", "\uc18c\ube44\uc790\ubb3c\uac00\uc9c0\uc218"],
        "negative_terms": ["\uc0dd\ud65c\ubb3c\uac00", "\uc2e0\uc120\uc2dd\ud488", "\ud488\ubaa9\ubcc4", "\uc9c0\ucd9c\ubaa9\uc801\ubcc4"],
        "required_all": [],
    },
    "PPI": {
        "keywords": ["\uc0dd\uc0b0\uc790\ubb3c\uac00\uc9c0\uc218", "\uc0dd\uc0b0\uc790\ubb3c\uac00", "PPI"],
        "preferred_cycle": "M",
        "terms": ["\uc0dd\uc0b0\uc790\ubb3c\uac00", "\uc0dd\uc0b0\uc790\ubb3c\uac00\uc9c0\uc218"],
        "item_terms": ["\ucd1d\uc9c0\uc218", "\uae30\ubcf8\ubd84\ub958", "\uc0dd\uc0b0\uc790\ubb3c\uac00\uc9c0\uc218"],
        "negative_terms": ["\uc218\ucd9c\uc785\ubb3c\uac00", "\uc6d0\uc7ac\ub8cc", "\uc911\uac04\uc7ac", "\ucd5c\uc885\uc7ac"],
        "required_all": [],
    },
    "CSI": {
        "keywords": ["\uc18c\ube44\uc790\uc2ec\ub9ac\uc9c0\uc218", "\uc18c\ube44\uc790\ub3d9\ud5a5", "\uc18c\ube44\uc790\ub3d9\ud5a5\uc870\uc0ac", "\uc2ec\ub9ac\uc9c0\uc218", "CSI"],
        "preferred_cycle": "M",
        "terms": ["\uc18c\ube44\uc790\uc2ec\ub9ac", "\uc18c\ube44\uc790\ub3d9\ud5a5"],
        "item_terms": ["\uc18c\ube44\uc790\uc2ec\ub9ac\uc9c0\uc218", "\uc18c\ube44\uc790\ub3d9\ud5a5", "\uc885\ud569"],
        "negative_terms": ["\uae30\ub300\uc778\ud50c\ub808\uc774\uc158", "\ud604\uc7ac\uc0dd\ud65c\ud615\ud3b8", "\uc18c\ube44\uc9c0\ucd9c\uc804\ub9dd", "BSI"],
        "required_all": [],
    },
    "BSI_MANUFACTURING": {
        "keywords": ["\uae30\uc5c5\uacbd\uae30\uc870\uc0ac\uc9c0\uc218", "\uc81c\uc870\uc5c5 BSI", "\uae30\uc5c5\uacbd\uae30", "BSI", "\uc5c5\ud669"],
        "preferred_cycle": "M",
        "terms": ["\uae30\uc5c5\uacbd\uae30", "\uc81c\uc870\uc5c5", "\uc5c5\ud669"],
        "item_terms": ["\uc81c\uc870\uc5c5", "\uc5c5\ud669", "BSI", "\uae30\uc5c5\uacbd\uae30\uc870\uc0ac"],
        "negative_terms": ["\ube44\uc81c\uc870\uc5c5", "\uc804\ub9dd", "\ub300\uae30\uc5c5", "\uc911\uc18c\uae30\uc5c5"],
        "required_all": [],
    },
}


class MarketIndicatorService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.bok_ecos = BokEcosProvider()
        self.fred = FredProvider()
        self.kosis = KosisProvider()

    @staticmethod
    def _as_bool(value: Any) -> bool:
        return bool(int(value or 0))

    def get_category_counts(self) -> dict[str, int]:
        rows = self.db.execute(
            text("""
                SELECT category, COUNT(*) AS count
                FROM market_indicators
                WHERE is_active = 1
                GROUP BY category
            """)
        ).mappings().all()
        return {str(row["category"]): int(row["count"] or 0) for row in rows}

    def list_indicators(self, *, category: str | None = None, active_only: bool = True) -> dict[str, Any]:
        clauses: list[str] = []
        params: dict[str, Any] = {}
        if active_only:
            clauses.append("is_active = 1")
        if category:
            clauses.append("category = :category")
            params["category"] = category
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.db.execute(
            text(
                f"""
                SELECT *
                FROM market_indicators
                {where_sql}
                ORDER BY display_order, indicator_name
                """
            ),
            params,
        ).mappings().all()
        return {"items": [self._indicator_item(row) for row in rows], "category_counts": self.get_category_counts()}

    def get_indicator(self, indicator_code: str) -> dict[str, Any]:
        row = self.db.execute(
            text("SELECT * FROM market_indicators WHERE indicator_code = :indicator_code"),
            {"indicator_code": indicator_code.strip().upper()},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="market indicator not found")
        return self._indicator_item(row)

    def get_indicator_values(self, indicator_code: str, *, start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
        indicator = self.get_indicator(indicator_code)
        clauses = ["indicator_code = :indicator_code"]
        params: dict[str, Any] = {"indicator_code": indicator["indicator_code"]}
        if start_date:
            clauses.append("value_date >= :start_date")
            params["start_date"] = start_date
        if end_date:
            clauses.append("value_date <= :end_date")
            params["end_date"] = end_date
        rows = self.db.execute(
            text(
                f"""
                SELECT *
                FROM market_indicator_values
                WHERE {' AND '.join(clauses)}
                ORDER BY value_date
                """
            ),
            params,
        ).mappings().all()
        return {"indicator_code": indicator["indicator_code"], "indicator_name": indicator["indicator_name"], "items": [self._value_item(row) for row in rows]}

    def list_readiness(self, *, indicator_codes: list[str] | None = None) -> dict[str, Any]:
        clauses = ["i.is_active = 1"]
        params: dict[str, Any] = {}
        if indicator_codes:
            normalized = [code.strip().upper() for code in indicator_codes if code and code.strip()]
            placeholders = ", ".join(f":code_{idx}" for idx, _ in enumerate(normalized))
            clauses.append(f"i.indicator_code IN ({placeholders})")
            params.update({f"code_{idx}": code for idx, code in enumerate(normalized)})
        rows = self.db.execute(
            text(
                f"""
                SELECT i.indicator_code, i.indicator_name, i.data_frequency, i.unit_label, i.collection_status,
                       i.latest_value, i.latest_value_date,
                       m.provider, m.provider_symbol, m.is_enabled, m.is_verified, m.last_test_status, m.last_test_message,
                       COALESCE(v.data_count, 0) AS data_count,
                       v.first_value_date, v.latest_value_date AS value_latest_date, v.latest_collected_at
                FROM market_indicators i
                LEFT JOIN market_indicator_provider_mappings m
                  ON m.indicator_code = i.indicator_code AND m.is_enabled = 1
                LEFT JOIN (
                    SELECT indicator_code,
                           COUNT(*) AS data_count,
                           MIN(value_date) AS first_value_date,
                           MAX(value_date) AS latest_value_date,
                           MAX(collected_at) AS latest_collected_at
                    FROM market_indicator_values
                    WHERE COALESCE(value, close_value) IS NOT NULL
                    GROUP BY indicator_code
                ) v ON v.indicator_code = i.indicator_code
                WHERE {' AND '.join(clauses)}
                ORDER BY i.display_order, i.indicator_code
                """
            ),
            params,
        ).mappings().all()
        items = [self._readiness_item(dict(row)) for row in rows]
        summary: dict[str, int] = {}
        for item in items:
            key = str(item["readiness"])
            summary[key] = summary.get(key, 0) + 1
        return {"items": items, "summary_counts": summary}

    def get_readiness(self, indicator_code: str) -> dict[str, Any]:
        result = self.list_readiness(indicator_codes=[indicator_code])
        if not result["items"]:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="market indicator readiness not found")
        return result["items"][0]

    def list_provider_mappings(self) -> dict[str, Any]:
        rows = self.db.execute(
            text(
                """
                SELECT m.*, i.indicator_name
                FROM market_indicator_provider_mappings m
                LEFT JOIN market_indicators i ON i.indicator_code = m.indicator_code
                ORDER BY i.display_order, m.provider
                """
            )
        ).mappings().all()
        return {"items": [self._mapping_item(row) for row in rows]}

    def get_ecos_table_list(self, *, parent_stat_code: str | None = None, start_index: int = 1, end_index: int = 100) -> dict[str, Any]:
        result = self.bok_ecos.table_list(parent_stat_code=parent_stat_code, start_index=start_index, end_index=end_index)
        return {
            "status": result.get("status") or "ERROR",
            "message": result.get("message") or "",
            "total_count": int(result.get("total_count") or result.get("list_total_count") or 0),
            "items": result.get("rows") or [],
        }

    def search_ecos_tables(
        self,
        *,
        keyword: str,
        parent_stat_code: str | None = None,
        max_depth: int = 2,
        cycle: str | None = None,
        only_searchable: bool = False,
    ) -> dict[str, Any]:
        result = self.bok_ecos.search_tables_by_keyword(
            keyword=keyword,
            parent_stat_code=parent_stat_code,
            max_depth=max(0, min(max_depth, 4)),
            cycle=cycle,
            only_searchable=only_searchable,
        )
        return {
            "keyword": keyword,
            "status": result.get("status") or "ERROR",
            "message": result.get("message") or "",
            "searched_count": int(result.get("searched_count") or 0),
            "items": result.get("items") or [],
        }

    def discover_ecos_candidates(self, payload: Any) -> dict[str, Any]:
        target_codes = getattr(payload, "indicator_codes", None) or list(ECOS_DISCOVERY_TARGETS.keys())
        target_codes = [code.strip().upper() for code in target_codes if code and code.strip()]
        max_depth = max(0, min(int(getattr(payload, "max_depth", 2) or 2), 4))
        requested_cycle = getattr(payload, "cycle", None)
        total_searched = 0
        items: list[dict[str, Any]] = []
        for indicator_code in target_codes:
            config = ECOS_DISCOVERY_TARGETS.get(indicator_code)
            if not config:
                continue
            indicator = self.get_indicator(indicator_code)
            rows_by_code: dict[str, dict[str, Any]] = {}
            for keyword in config["keywords"]:
                result = self.bok_ecos.search_tables_by_keyword(
                    keyword=keyword,
                    max_depth=max_depth,
                    cycle=requested_cycle,
                    only_searchable=False,
                )
                total_searched += int(result.get("searched_count") or 0)
                for row in result.get("items") or []:
                    stat_code = str(row.get("stat_code") or "")
                    if stat_code:
                        rows_by_code[stat_code] = row
            candidates = [self._score_ecos_candidate(indicator_code, row) for row in rows_by_code.values()]
            candidates = sorted(candidates, key=lambda row: (-int(row.get("score") or 0), str(row.get("stat_name") or "")))[:20]
            items.append(
                {
                    "indicator_code": indicator_code,
                    "indicator_name": indicator.get("indicator_name"),
                    "keywords": config["keywords"],
                    "candidates": candidates,
                }
            )
        return {
            "status": "SUCCESS",
            "message": "ECOS candidate discovery completed. Candidates are not activated automatically.",
            "searched_count": total_searched,
            "items": items,
        }

    def discover_ecos_mapping_candidates(self, payload: Any) -> dict[str, Any]:
        target_codes = getattr(payload, "indicator_codes", None) or list(ECOS_DISCOVERY_TARGETS.keys())
        target_codes = [code.strip().upper() for code in target_codes if code and code.strip()]
        top_table_count = max(1, min(int(getattr(payload, "top_table_count", 5) or 5), 5))
        max_item_count = max(20, min(int(getattr(payload, "max_item_count", 200) or 200), 300))
        table_payload = type("Payload", (), {"indicator_codes": target_codes, "max_depth": 2, "cycle": None})()
        table_result = self.discover_ecos_candidates(table_payload)
        items: list[dict[str, Any]] = []
        for group in table_result.get("items") or []:
            indicator_code = str(group.get("indicator_code") or "")
            indicator_name = group.get("indicator_name")
            mapping_candidates: list[dict[str, Any]] = []
            for table in (group.get("candidates") or [])[:top_table_count]:
                stat_code = str(table.get("stat_code") or "")
                if not stat_code or str(table.get("srch_yn") or "").upper() != "Y":
                    continue
                item_result = self.bok_ecos.item_list(stat_code, start_index=1, end_index=max_item_count)
                if item_result.get("status") != "SUCCESS":
                    continue
                for raw_item in item_result.get("rows") or []:
                    candidate = self._build_mapping_candidate(indicator_code, indicator_name, table, raw_item)
                    if candidate:
                        mapping_candidates.append(candidate)
            unique_candidates: dict[tuple[str, str], dict[str, Any]] = {}
            for candidate in mapping_candidates:
                key = (str(candidate.get("stat_code") or ""), str(candidate.get("item_code1") or ""))
                if key not in unique_candidates or int(candidate.get("score") or 0) > int(unique_candidates[key].get("score") or 0):
                    unique_candidates[key] = candidate
            mapping_candidates = sorted(unique_candidates.values(), key=lambda row: (-int(row.get("score") or 0), str(row.get("stat_name") or ""), str(row.get("item_name1") or "")))[:10]
            items.append({"indicator_code": indicator_code, "indicator_name": indicator_name, "candidates": mapping_candidates})
        return {"status": "SUCCESS", "message": "ECOS mapping candidates generated. Candidates are not activated automatically.", "items": items}

    def test_ecos_mapping_candidate(self, indicator_code: str, payload: Any) -> dict[str, Any]:
        indicator = self.get_indicator(indicator_code)
        params = {
            "stat_code": getattr(payload, "stat_code"),
            "cycle": getattr(payload, "cycle", "D") or "D",
            "item_code1": getattr(payload, "item_code1"),
            "item_name1": getattr(payload, "item_name1", None),
            "value_field": "DATA_VALUE",
            "scale": getattr(payload, "scale", 1),
            "source_unit": getattr(payload, "source_unit", None),
            "date_format": "ECOS_TIME",
        }
        mapping = {
            "indicator_code": indicator["indicator_code"],
            "provider": "BOK_ECOS",
            "api_type": "STATISTIC_SEARCH",
            "api_id": "ECOS_STATISTIC_SEARCH",
            "endpoint_url": "/api/StatisticSearch",
            "provider_symbol": f"{params['stat_code']}:{params['item_code1']}",
            "request_params_json": params,
        }
        test_days = 370 * 5 if str(params.get("cycle") or "").upper() == "M" or indicator.get("data_frequency") == "MONTHLY" else 90
        result = self.bok_ecos.test_mapping(mapping, start_date=(date.today() - timedelta(days=test_days)).isoformat(), end_date=date.today().isoformat())
        rows = result.get("rows") or []
        return {
            "indicator_code": indicator["indicator_code"],
            "provider": "BOK_ECOS",
            "status": str(result.get("status") or "ERROR").upper(),
            "message": str(result.get("message") or "")[:500],
            "sample_count": len(rows),
            "sample_rows": rows[:5],
        }

    def get_ecos_item_list(self, stat_code: str, *, start_index: int = 1, end_index: int = 100) -> dict[str, Any]:
        result = self.bok_ecos.item_list(stat_code, start_index=start_index, end_index=end_index)
        return {
            "stat_code": stat_code,
            "status": result.get("status") or "ERROR",
            "message": result.get("message") or "",
            "list_total_count": int(result.get("list_total_count") or 0),
            "items": result.get("rows") or [],
        }

    def upsert_provider_mapping(self, indicator_code: str, payload: Any) -> dict[str, Any]:
        indicator = self.get_indicator(indicator_code)
        provider = str(getattr(payload, "provider", None) or "BOK_ECOS").strip().upper()
        params_json = self._params_to_json(getattr(payload, "request_params_json", None))
        is_enabled = 1 if bool(getattr(payload, "is_enabled", False)) else 0
        self.db.execute(
            text(
                """
                INSERT INTO market_indicator_provider_mappings
                (indicator_code, provider, api_type, api_id, endpoint_url, provider_symbol, request_params_json,
                 is_enabled, is_verified, last_test_status, last_test_message, created_at, updated_at)
                VALUES (:indicator_code, :provider, :api_type, :api_id, :endpoint_url, :provider_symbol, :request_params_json,
                        :is_enabled, 0, 'WAITING', 'provider mapping check required', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(indicator_code, provider) DO UPDATE SET
                    api_type = excluded.api_type,
                    api_id = excluded.api_id,
                    endpoint_url = excluded.endpoint_url,
                    provider_symbol = excluded.provider_symbol,
                    request_params_json = excluded.request_params_json,
                    is_enabled = CASE WHEN market_indicator_provider_mappings.is_verified = 1 THEN excluded.is_enabled ELSE 0 END,
                    is_verified = 0,
                    verified_at = NULL,
                    last_test_status = 'WAITING',
                    last_test_message = 'provider mapping check required',
                    updated_at = CURRENT_TIMESTAMP
                """
            ),
            {
                "indicator_code": indicator["indicator_code"],
                "provider": provider,
                "api_type": getattr(payload, "api_type", None) or "ECONOMIC_STAT",
                "api_id": getattr(payload, "api_id", None),
                "endpoint_url": getattr(payload, "endpoint_url", None),
                "provider_symbol": getattr(payload, "provider_symbol", None),
                "request_params_json": params_json,
                "is_enabled": is_enabled,
            },
        )
        self.db.commit()
        return self._get_mapping(indicator["indicator_code"], provider)

    def test_provider_mapping(self, indicator_code: str, payload: Any) -> dict[str, Any]:
        indicator = self.get_indicator(indicator_code)
        provider = self._preferred_provider(indicator)
        mapping = self._get_mapping(indicator["indicator_code"], provider)
        result = self._provider_client(provider).test_mapping(mapping, start_date=getattr(payload, "start_date", None), end_date=getattr(payload, "end_date", None))
        status_value = str(result.get("status") or "ERROR").upper()
        message = str(result.get("message") or "")[:500]
        success = status_value == "SUCCESS"
        if getattr(payload, "save_result", True):
            self.db.execute(
                text(
                    """
                    UPDATE market_indicator_provider_mappings
                    SET is_verified = :is_verified,
                        verified_at = CASE WHEN :is_verified = 1 THEN CURRENT_TIMESTAMP ELSE NULL END,
                        last_test_status = :status,
                        last_test_message = :message,
                        last_tested_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE indicator_code = :indicator_code AND provider = :provider
                    """
                ),
                {"indicator_code": indicator["indicator_code"], "provider": provider, "is_verified": 1 if success else 0, "status": status_value, "message": message},
            )
            self.db.commit()
        rows = result.get("rows") or []
        return {
            "indicator_code": indicator["indicator_code"],
            "provider": provider,
            "status": status_value,
            "message": message,
            "sample_count": len(rows),
            "sample_rows": rows[:5],
        }

    def activate_provider_mapping(self, indicator_code: str) -> dict[str, Any]:
        indicator = self.get_indicator(indicator_code)
        provider = self._preferred_provider(indicator)
        mapping = self._get_mapping(indicator["indicator_code"], provider)
        if not mapping.get("is_verified"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="provider mapping must be tested successfully before activation")
        self.db.execute(
            text(
                """
                UPDATE market_indicator_provider_mappings
                SET is_enabled = 1, updated_at = CURRENT_TIMESTAMP
                WHERE indicator_code = :indicator_code AND provider = :provider
                """
            ),
            {"indicator_code": indicator["indicator_code"], "provider": provider},
        )
        self.db.execute(
            text(
                """
                UPDATE market_indicators
                SET collection_status = CASE WHEN collection_status = 'WAITING' THEN 'NOT_COLLECTED' ELSE collection_status END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE indicator_code = :indicator_code
                """
            ),
            {"indicator_code": indicator["indicator_code"]},
        )
        self.db.commit()
        return self._get_mapping(indicator["indicator_code"], provider)

    def collect_indicator(
        self,
        indicator_codes: list[str] | None = None,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        skip_error_status: bool = False,
    ) -> dict[str, Any]:
        targets = self._collection_targets(indicator_codes)
        date_to = end_date or date.today().isoformat()
        results: list[dict[str, Any]] = []
        success_count = 0
        waiting_count = 0
        skipped_count = 0
        failed_count = 0
        for code in targets:
            try:
                master = self.get_indicator(code)
                if skip_error_status and str(master.get("collection_status") or "").upper() == "ERROR":
                    skipped_count += 1
                    results.append({"indicator_code": code, "status": "SKIPPED", "message": "previous ERROR is skipped by incremental all policy", "saved_count": 0})
                    continue
                date_from, mode = self._resolve_collect_window(
                    item_type="INDICATOR",
                    item_code=code,
                    frequency=str(master.get("data_frequency") or "DAILY"),
                    start_date=start_date,
                    end_date=end_date,
                    latest_date=self._latest_value_date(code),
                )
                mapping = self._get_enabled_mapping(code)
                if not mapping:
                    waiting_count += 1
                    results.append({"indicator_code": code, "status": "WAITING", "message": "enabled and verified provider mapping is required", "saved_count": 0})
                    continue
                provider = str(mapping.get("provider") or "").upper()
                if provider == "DERIVED":
                    values = self._collect_derived_values(code, start_date=date_from, end_date=date_to)
                else:
                    values = self._provider_client(provider).collect_values(code, mapping, start_date=date_from, end_date=date_to)
                if not values:
                    waiting_count += 1
                    self._mark_indicator_status(code, "WAITING")
                    results.append({"indicator_code": code, "status": "WAITING", "message": f"{provider} returned no collectable rows", "saved_count": 0})
                    continue
                counts = self._upsert_values(values)
                latest = values[-1]
                self._update_indicator_latest(code, latest)
                success_count += 1
                results.append(
                    {
                        "indicator_code": code,
                        "status": "SUCCESS",
                        "message": f"{mode}: received {len(values)} {provider} rows, inserted {counts['inserted_count']}, updated {counts['updated_count']}, unchanged {counts['unchanged_count']}",
                        "saved_count": counts["inserted_count"] + counts["updated_count"],
                        "received_count": len(values),
                        "inserted_count": counts["inserted_count"],
                        "updated_count": counts["updated_count"],
                        "unchanged_count": counts["unchanged_count"],
                        "requested_from": date_from,
                        "requested_to": date_to,
                        "latest_value": latest.get("value"),
                        "latest_value_date": latest.get("value_date"),
                    }
                )
            except Exception as exc:  # noqa: BLE001 - collect endpoint must isolate per-indicator failures.
                failed_count += 1
                self._mark_indicator_status(code, "ERROR")
                results.append({"indicator_code": code, "status": "ERROR", "message": str(exc)[:500], "saved_count": 0})
        self.db.commit()
        return {
            "requested_count": len(results),
            "success_count": success_count,
            "waiting_count": waiting_count,
            "skipped_count": skipped_count,
            "failed_count": failed_count,
            "message": f"market indicator collection completed: success {success_count}, waiting {waiting_count}, failed {failed_count}.",
            "results": results,
        }

    def _resolve_collect_window(
        self,
        *,
        item_type: str,
        item_code: str,
        frequency: str,
        start_date: str | None,
        end_date: str | None,
        latest_date: str | None,
    ) -> tuple[str, str]:
        if start_date or end_date:
            return (start_date or self._initial_start_date(item_type, item_code, frequency), "manual_range")
        if latest_date:
            return self._apply_overlap(latest_date, item_type, item_code, frequency), "incremental_overlap"
        return self._initial_start_date(item_type, item_code, frequency), "initial_backfill"

    def _policy(self, item_type: str, item_code: str) -> dict[str, Any]:
        row = self.db.execute(
            text(
                """
                SELECT *
                FROM market_data_collection_policies
                WHERE item_type = :item_type AND item_code = :item_code
                """
            ),
            {"item_type": item_type.upper(), "item_code": item_code.upper()},
        ).mappings().first()
        return dict(row) if row else {}

    def _initial_start_date(self, item_type: str, item_code: str, frequency: str) -> str:
        policy = self._policy(item_type, item_code)
        value = int(policy.get("initial_lookback_value") or 5)
        unit = str(policy.get("initial_lookback_unit") or "YEARS").upper()
        today = date.today()
        if unit.startswith("YEAR"):
            return (today - timedelta(days=365 * value)).isoformat()
        if unit.startswith("MONTH"):
            return self._add_months(today, -value).isoformat()
        if unit.startswith("QUARTER"):
            return self._add_months(today, -value * 3).isoformat()
        return (today - timedelta(days=value)).isoformat()

    def _apply_overlap(self, latest_date: str, item_type: str, item_code: str, frequency: str) -> str:
        policy = self._policy(item_type, item_code)
        value = int(policy.get("overlap_value") or (6 if frequency.upper() == "MONTHLY" else 10))
        unit = str(policy.get("overlap_unit") or ("MONTHS" if frequency.upper() == "MONTHLY" else "DAYS")).upper()
        base = datetime.strptime(str(latest_date)[:10], "%Y-%m-%d").date()
        if unit.startswith("MONTH"):
            return self._add_months(base, -value).isoformat()
        if unit.startswith("QUARTER"):
            return self._add_months(base, -value * 3).isoformat()
        if unit.startswith("WEEK"):
            return (base - timedelta(weeks=value)).isoformat()
        return (base - timedelta(days=value)).isoformat()

    @staticmethod
    def _add_months(source: date, months: int) -> date:
        month_index = source.year * 12 + source.month - 1 + months
        year = month_index // 12
        month = month_index % 12 + 1
        day = min(source.day, 28)
        return date(year, month, day)

    def _build_mapping_candidate(self, indicator_code: str, indicator_name: str | None, table: dict[str, Any], raw_item: dict[str, Any]) -> dict[str, Any] | None:
        item_code = self._first_text(raw_item, "ITEM_CODE", "ITEM_CODE1", "CODE", "item_code", "item_code1")
        item_name = self._first_text(raw_item, "ITEM_NAME", "ITEM_NAME1", "NAME", "item_name", "item_name1")
        if not item_code or not item_name:
            return None
        score, reason = self._score_ecos_item(indicator_code, table, item_name)
        if score <= 0:
            return None
        stat_code = str(table.get("stat_code") or "")
        cycle = str(table.get("cycle") or ECOS_DISCOVERY_TARGETS[indicator_code].get("preferred_cycle") or "D")
        source_unit = self._first_text(raw_item, "UNIT_NAME", "unit_name")
        params = {
            "stat_code": stat_code,
            "cycle": cycle,
            "item_code1": item_code,
            "item_name1": item_name,
            "value_field": "DATA_VALUE",
            "scale": 1,
            "source_unit": source_unit,
            "date_format": "ECOS_TIME",
        }
        return {
            "indicator_code": indicator_code,
            "indicator_name": indicator_name,
            "stat_code": stat_code,
            "stat_name": table.get("stat_name"),
            "cycle": cycle,
            "item_code1": item_code,
            "item_name1": item_name,
            "provider_symbol": f"{stat_code}:{item_code}",
            "score": score + int(table.get("score") or 0),
            "reason": reason,
            "source_unit": source_unit,
            "request_params_json": params,
        }

    def _score_ecos_item(self, indicator_code: str, table: dict[str, Any], item_name: str) -> tuple[int, str]:
        config = ECOS_DISCOVERY_TARGETS[indicator_code]
        item_lower = item_name.lower()
        stat_lower = str(table.get("stat_name") or "").lower()
        cycle = str(table.get("cycle") or "").upper()
        score = 0
        reasons: list[str] = []
        missing_required = [term for term in config.get("required_all", []) if term.lower() not in item_lower]
        if missing_required:
            score -= 160
            reasons.append("missing required " + ", ".join(missing_required))
        for term in config.get("item_terms", []):
            if term.lower() in item_lower:
                score += 50 if score == 0 else 20
                reasons.append(f"item contains {term}")
        for term in config.get("negative_terms", []):
            if term.lower() in item_lower:
                score -= 10
                reasons.append(f"negative term {term}")
        if indicator_code in {"USD_KRW", "JPY_KRW", "CNY_KRW"}:
            if "\ub9e4\ub9e4\uae30\uc900\uc728" in item_lower:
                score += 80
                reasons.append("base exchange rate")
            for trade_term in ("\uc2dc\uac00", "\uace0\uac00", "\uc800\uac00", "\uc885\uac00"):
                if trade_term in item_lower:
                    score -= 80
                    reasons.append(f"trading quote {trade_term}")
        if "\ud658\uc728" in stat_lower:
            score += 20
            reasons.append("exchange-rate table")
        if "\uae08\ub9ac" in stat_lower or "\uc2dc\uc7a5\uae08\ub9ac" in stat_lower:
            score += 20
            reasons.append("interest-rate table")
        preferred_cycle = str(config.get("preferred_cycle") or "").upper()
        if preferred_cycle and cycle == preferred_cycle:
            score += 15
            reasons.append(f"cycle {cycle}")
        if indicator_code == "CALL_RATE":
            if "\uc804\uccb4\uac70\ub798" in item_lower:
                score += 30
                reasons.append("whole market call rate")
            if "\ucc28\uc785" in item_lower or "\uc911\uac1c\ud68c\uc0ac" in item_lower:
                score -= 20
                reasons.append("specific call-rate segment")
        if indicator_code in {"CPI", "PPI"}:
            if "\ucd1d\uc9c0\uc218" in item_lower:
                score += 60
                reasons.append("headline total index")
            if "\uc804\uad6d" in item_lower:
                score += 25
                reasons.append("national series")
            if "\uc9c0\uc218" in item_lower and ("\uc804\ub144" in item_lower or "\uc804\uc6d4" in item_lower):
                score -= 20
                reasons.append("rate-of-change item, prefer level index")
        if indicator_code == "CSI":
            if "\uc18c\ube44\uc790\uc2ec\ub9ac\uc9c0\uc218" in item_lower or "\uc18c\ube44\uc790\uc2ec\ub9ac\uc9c0\uc218" in stat_lower:
                score += 80
                reasons.append("consumer sentiment index")
            if "\uc885\ud569" in item_lower:
                score += 25
                reasons.append("composite sentiment")
        if indicator_code == "BSI_MANUFACTURING":
            if "\uc81c\uc870\uc5c5" in item_lower or "\uc81c\uc870\uc5c5" in stat_lower:
                score += 55
                reasons.append("manufacturing series")
            if "\uc5c5\ud669" in item_lower:
                score += 50
                reasons.append("business condition BSI")
            if "\ube44\uc81c\uc870\uc5c5" in item_lower:
                score -= 80
                reasons.append("non-manufacturing series")
            if "\uc804\ub9dd" in item_lower:
                score -= 25
                reasons.append("outlook item")
        if len(item_name) <= 1:
            score -= 10
            reasons.append("too broad item")
        return score, "; ".join(reasons)

    def _first_text(self, row: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = row.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return None

    def _score_ecos_candidate(self, indicator_code: str, row: dict[str, Any]) -> dict[str, Any]:
        config = ECOS_DISCOVERY_TARGETS[indicator_code]
        stat_name = str(row.get("stat_name") or "")
        stat_name_lower = stat_name.lower()
        cycle = str(row.get("cycle") or "").upper()
        srch_yn = str(row.get("srch_yn") or "").upper()
        org_name = str(row.get("org_name") or "")
        score = 0
        reasons: list[str] = []
        for keyword in config["keywords"]:
            if keyword.lower() in stat_name_lower:
                score += 50
                reasons.append(f"name contains {keyword}")
        if srch_yn == "Y":
            score += 20
            reasons.append("searchable")
        else:
            score -= 30
            reasons.append("not searchable")
        preferred_cycle = str(config.get("preferred_cycle") or "").upper()
        if preferred_cycle and cycle == preferred_cycle:
            score += 15
            reasons.append(f"cycle {cycle}")
        elif preferred_cycle and cycle:
            score -= 10
            reasons.append(f"cycle {cycle} differs from {preferred_cycle}")
        if "\ud55c\uad6d\uc740\ud589" in org_name:
            score += 10
            reasons.append("BOK source")
        matched_terms = [term for term in config["terms"] if term.lower() in stat_name_lower]
        if matched_terms:
            score += 20
            reasons.append("terms " + ", ".join(matched_terms))
        for term in config.get("negative_terms", []):
            if term.lower() in stat_name_lower:
                score -= 10
                reasons.append(f"negative table term {term}")
        if indicator_code in {"CPI", "PPI", "CSI", "BSI_MANUFACTURING"} and cycle == "M":
            score += 20
            reasons.append("monthly macro table")
        if indicator_code == "CSI" and "\uc18c\ube44\uc790\uc2ec\ub9ac" in stat_name_lower:
            score += 50
            reasons.append("consumer sentiment table")
        if indicator_code == "BSI_MANUFACTURING" and "\uae30\uc5c5\uacbd\uae30" in stat_name_lower:
            score += 30
            reasons.append("business survey table")
        if len(stat_name) <= 6 and srch_yn != "Y":
            score -= 10
            reasons.append("broad parent table")
        return {**row, "score": score, "reason": "; ".join(reasons)}

    def _collection_targets(self, indicator_codes: list[str] | None) -> list[str]:
        if indicator_codes:
            return [code.strip().upper() for code in indicator_codes if code and code.strip()]
        rows = self.db.execute(
            text(
                """
                SELECT indicator_code
                FROM market_indicators
                WHERE is_active = 1 AND category IN ('FX', 'RATE', 'INFLATION', 'ECONOMY', 'GLOBAL_INDEX', 'GLOBAL_RATE')
                ORDER BY display_order
                """
            )
        ).mappings().all()
        return [str(row["indicator_code"]) for row in rows]

    def _preferred_provider(self, indicator: dict[str, Any]) -> str:
        code = str(indicator.get("indicator_code") or "").upper()
        category = str(indicator.get("category") or "").upper()
        if code.startswith("US_") or category in {"GLOBAL_INDEX", "GLOBAL_RATE"}:
            return "FRED"
        return "BOK_ECOS"

    def _provider_client(self, provider: str):
        normalized = str(provider or "").upper()
        if normalized == "FRED":
            return self.fred
        if normalized == "BOK_ECOS":
            return self.bok_ecos
        if normalized == "KOSIS":
            return self.kosis
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"unsupported provider: {provider}")

    def _collect_derived_values(self, indicator_code: str, *, start_date: str, end_date: str) -> list[dict[str, Any]]:
        row = self.db.execute(
            text("SELECT * FROM market_indicator_derivations WHERE indicator_code = :code AND is_active = 1"),
            {"code": indicator_code.strip().upper()},
        ).mappings().first()
        if not row:
            raise RuntimeError("derived formula is not configured")
        formula = str(row["formula_type"]).upper()
        sources = json.loads(str(row["source_codes_json"] or "[]"))
        source_values = {code: self._source_value_map(str(code), start_date=start_date, end_date=end_date) for code in sources}
        values: list[dict[str, Any]] = []

        def emit(value_date: str, value: float | None, period_label: str | None = None) -> None:
            if value is None or not math.isfinite(float(value)):
                return
            values.append(
                {
                    "indicator_code": indicator_code,
                    "value_date": value_date,
                    "period_label": period_label,
                    "value": round(float(value), 6),
                    "change_value": None,
                    "change_pct": None,
                    "mom_pct": None,
                    "yoy_pct": None,
                    "source_provider": "DERIVED",
                    "source_unit": None,
                    "is_preliminary": 0,
                    "release_date": None,
                    "raw_payload_json": None,
                }
            )

        if formula in {"US_10Y_MINUS_US_2Y", "KR_10Y_MINUS_KR_3Y"} and len(sources) >= 2:
            left, right = source_values[sources[0]], source_values[sources[1]]
            for value_date in sorted(set(left).intersection(right)):
                emit(value_date, left[value_date]["value"] - right[value_date]["value"])
        elif formula in {"BASE_RATE_MINUS_CPI_YOY", "FED_FUNDS_MINUS_CORE_PCE_YOY"} and len(sources) >= 2:
            rate_map, inflation_map = source_values[sources[0]], source_values[sources[1]]
            rate_dates = sorted(rate_map)
            for value_date in sorted(inflation_map):
                inflation = inflation_map[value_date]
                inflation_yoy = inflation.get("yoy_pct")
                if inflation_yoy is None:
                    continue
                rate_date = self._latest_key_on_or_before(rate_dates, value_date)
                if not rate_date:
                    continue
                emit(value_date, rate_map[rate_date]["value"] - float(inflation_yoy), value_date[:7])
        elif formula == "ROLLING_RETURN_STD_20D" and sources:
            rows = sorted(source_values[sources[0]].items())
            returns: list[tuple[str, float]] = []
            for idx in range(1, len(rows)):
                prev_value = rows[idx - 1][1]["value"]
                value = rows[idx][1]["value"]
                if prev_value:
                    returns.append((rows[idx][0], (value / prev_value - 1) * 100))
            for idx in range(19, len(returns)):
                window = [item[1] for item in returns[idx - 19 : idx + 1]]
                mean = sum(window) / len(window)
                variance = sum((item - mean) ** 2 for item in window) / len(window)
                emit(returns[idx][0], math.sqrt(variance))
        elif formula == "RATIO_X100" and len(sources) >= 2:
            left, right = source_values[sources[0]], source_values[sources[1]]
            for value_date in sorted(set(left).intersection(right)):
                denominator = right[value_date]["value"]
                if denominator:
                    emit(value_date, left[value_date]["value"] / denominator * 100)
        else:
            raise RuntimeError(f"unsupported derived formula: {formula}")

        return values

    @staticmethod
    def _latest_key_on_or_before(sorted_keys: list[str], target_key: str) -> str | None:
        latest: str | None = None
        for key in sorted_keys:
            if key > target_key:
                break
            latest = key
        return latest

    def _source_value_map(self, indicator_code: str, *, start_date: str, end_date: str) -> dict[str, dict[str, float | str | None]]:
        rows = self.db.execute(
            text(
                """
                SELECT value_date, period_label, value, close_value, yoy_pct
                FROM market_indicator_values
                WHERE indicator_code = :code
                  AND value_date BETWEEN :start_date AND :end_date
                ORDER BY value_date
                """
            ),
            {"code": indicator_code.strip().upper(), "start_date": start_date, "end_date": end_date},
        ).mappings().all()
        result: dict[str, dict[str, float | str | None]] = {}
        for row in rows:
            value = row["value"] if row["value"] is not None else row["close_value"]
            if value is None:
                continue
            result[str(row["value_date"])] = {
                "value": float(value),
                "period_label": row.get("period_label"),
                "yoy_pct": float(row["yoy_pct"]) if row["yoy_pct"] is not None else None,
            }
        return result

    def _get_mapping(self, indicator_code: str, provider: str) -> dict[str, Any]:
        row = self.db.execute(
            text(
                """
                SELECT m.*, i.indicator_name
                FROM market_indicator_provider_mappings m
                LEFT JOIN market_indicators i ON i.indicator_code = m.indicator_code
                WHERE m.indicator_code = :indicator_code AND m.provider = :provider
                """
            ),
            {"indicator_code": indicator_code.strip().upper(), "provider": provider.strip().upper()},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="provider mapping not found")
        return self._mapping_item(row)

    def _get_enabled_mapping(self, indicator_code: str) -> dict[str, Any] | None:
        row = self.db.execute(
            text(
                """
                SELECT m.*, i.indicator_name
                FROM market_indicator_provider_mappings m
                LEFT JOIN market_indicators i ON i.indicator_code = m.indicator_code
                WHERE m.indicator_code = :indicator_code
                  AND m.is_enabled = 1
                  AND m.is_verified = 1
                ORDER BY CASE m.provider WHEN 'FRED' THEN 1 WHEN 'BOK_ECOS' THEN 2 ELSE 9 END
                LIMIT 1
                """
            ),
            {"indicator_code": indicator_code.strip().upper()},
        ).mappings().first()
        return self._mapping_item(row) if row else None

    def _upsert_value(self, value: dict[str, Any]) -> None:
        self.db.execute(
            text(
                """
                INSERT INTO market_indicator_values
                (indicator_code, value_date, period_label, value, change_value, change_pct, mom_pct, yoy_pct, source_provider, source_unit,
                 is_preliminary, release_date, raw_payload_json, created_at, updated_at)
                VALUES (:indicator_code, :value_date, :period_label, :value, :change_value, :change_pct, :mom_pct, :yoy_pct, :source_provider,
                        :source_unit, :is_preliminary, :release_date, :raw_payload_json, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(indicator_code, value_date) DO UPDATE SET
                    period_label = excluded.period_label,
                    value = excluded.value,
                    change_value = excluded.change_value,
                    change_pct = excluded.change_pct,
                    mom_pct = excluded.mom_pct,
                    yoy_pct = excluded.yoy_pct,
                    source_provider = excluded.source_provider,
                    source_unit = excluded.source_unit,
                    is_preliminary = excluded.is_preliminary,
                    release_date = excluded.release_date,
                    raw_payload_json = excluded.raw_payload_json,
                    updated_at = CURRENT_TIMESTAMP
                """
            ),
            value,
        )

    def _upsert_values(self, values: list[dict[str, Any]]) -> dict[str, int]:
        if not values:
            return {"inserted_count": 0, "updated_count": 0, "unchanged_count": 0}
        inserted = 0
        updated = 0
        unchanged = 0
        normalized: list[dict[str, Any]] = []
        for value in values:
            existing = self.db.execute(
                text(
                    """
                    SELECT value, change_value, change_pct, mom_pct, yoy_pct, source_unit
                    FROM market_indicator_values
                    WHERE indicator_code = :indicator_code AND value_date = :value_date
                    """
                ),
                {"indicator_code": value.get("indicator_code"), "value_date": value.get("value_date")},
            ).mappings().first()
            value = {**value, "raw_payload_json": None}
            normalized.append(value)
            if not existing:
                inserted += 1
                value["revised_at"] = None
                continue
            comparable_keys = ("value", "change_value", "change_pct", "mom_pct", "yoy_pct", "source_unit")
            changed = any((existing.get(key) != value.get(key)) for key in comparable_keys)
            if changed:
                updated += 1
                value["revised_at"] = datetime.now().isoformat(timespec="seconds")
            else:
                unchanged += 1
                value["revised_at"] = None
        self.db.execute(
            text(
                """
                INSERT INTO market_indicator_values
                (indicator_code, value_date, period_label, value, change_value, change_pct, mom_pct, yoy_pct, source_provider, source_unit,
                 is_preliminary, release_date, raw_payload_json, collected_at, revised_at, created_at, updated_at)
                VALUES (:indicator_code, :value_date, :period_label, :value, :change_value, :change_pct, :mom_pct, :yoy_pct, :source_provider,
                        :source_unit, :is_preliminary, :release_date, NULL, CURRENT_TIMESTAMP, :revised_at, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(indicator_code, value_date) DO UPDATE SET
                    period_label = excluded.period_label,
                    value = excluded.value,
                    change_value = excluded.change_value,
                    change_pct = excluded.change_pct,
                    mom_pct = excluded.mom_pct,
                    yoy_pct = excluded.yoy_pct,
                    source_provider = excluded.source_provider,
                    source_unit = excluded.source_unit,
                    is_preliminary = excluded.is_preliminary,
                    release_date = excluded.release_date,
                    raw_payload_json = NULL,
                    collected_at = CURRENT_TIMESTAMP,
                    revised_at = COALESCE(excluded.revised_at, market_indicator_values.revised_at),
                    updated_at = CASE
                        WHEN market_indicator_values.value IS NOT excluded.value
                          OR market_indicator_values.change_value IS NOT excluded.change_value
                          OR market_indicator_values.change_pct IS NOT excluded.change_pct
                          OR market_indicator_values.mom_pct IS NOT excluded.mom_pct
                          OR market_indicator_values.yoy_pct IS NOT excluded.yoy_pct
                          OR COALESCE(market_indicator_values.source_unit, '') <> COALESCE(excluded.source_unit, '')
                        THEN CURRENT_TIMESTAMP
                        ELSE market_indicator_values.updated_at
                    END
                """
            ),
            normalized,
        )
        return {"inserted_count": inserted, "updated_count": updated, "unchanged_count": unchanged}

    def _latest_value_date(self, indicator_code: str) -> str | None:
        return self.db.execute(
            text("SELECT MAX(value_date) FROM market_indicator_values WHERE indicator_code = :code"),
            {"code": indicator_code.strip().upper()},
        ).scalar()

    def _update_indicator_latest(self, indicator_code: str, latest: dict[str, Any]) -> None:
        self.db.execute(
            text(
                """
                UPDATE market_indicators
                SET collection_status = 'LATEST',
                    latest_value = :latest_value,
                    latest_value_date = :latest_value_date,
                    latest_change_value = :latest_change_value,
                    latest_change_pct = :latest_change_pct,
                    latest_mom_pct = :latest_mom_pct,
                    latest_yoy_pct = :latest_yoy_pct,
                    updated_at = CURRENT_TIMESTAMP
                WHERE indicator_code = :indicator_code
                """
            ),
            {
                "indicator_code": indicator_code,
                "latest_value": latest.get("value"),
                "latest_value_date": latest.get("value_date"),
                "latest_change_value": latest.get("change_value"),
                "latest_change_pct": latest.get("change_pct"),
                "latest_mom_pct": latest.get("mom_pct"),
                "latest_yoy_pct": latest.get("yoy_pct"),
            },
        )

    def _mark_indicator_status(self, indicator_code: str, collection_status: str) -> None:
        self.db.execute(
            text("UPDATE market_indicators SET collection_status = :collection_status, updated_at = CURRENT_TIMESTAMP WHERE indicator_code = :indicator_code"),
            {"indicator_code": indicator_code, "collection_status": collection_status},
        )

    def _params_to_json(self, value: Any) -> str:
        if value is None:
            return "{}"
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                parsed = {"raw": value}
            return json.dumps(parsed, ensure_ascii=False, sort_keys=True)
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    def _indicator_item(self, row: Any) -> dict[str, Any]:
        item = dict(row)
        item["is_active"] = self._as_bool(item.get("is_active"))
        return item

    def _value_item(self, row: Any) -> dict[str, Any]:
        item = dict(row)
        item["is_preliminary"] = self._as_bool(item.get("is_preliminary"))
        item.pop("raw_payload_json", None)
        item.pop("created_at", None)
        item.pop("updated_at", None)
        return item

    def _readiness_item(self, row: dict[str, Any]) -> dict[str, Any]:
        data_count = int(row.get("data_count") or 0)
        mapping_ready = self._as_bool(row.get("is_enabled")) and self._as_bool(row.get("is_verified"))
        data_ready = data_count > 0
        signal_min = self._signal_minimum_rows(str(row.get("data_frequency") or "DAILY"), str(row.get("indicator_code") or ""))
        signal_ready = data_count >= signal_min
        status_value = str(row.get("collection_status") or "").upper()
        if status_value == "ERROR":
            readiness = "ERROR"
            reason = row.get("last_test_message") or "collection status is ERROR"
        elif signal_ready:
            readiness = "SIGNAL_READY"
            reason = None
        elif data_ready:
            readiness = "COMPARE_READY"
            reason = f"data exists but signal transforms need at least {signal_min} rows"
        elif mapping_ready:
            readiness = "MAPPING_READY"
            reason = "provider mapping is active; collection has no stored values yet"
        else:
            readiness = "MASTER_ONLY"
            reason = "active and verified provider mapping is required"
        return {
            "indicator_code": row.get("indicator_code"),
            "indicator_name": row.get("indicator_name"),
            "provider": row.get("provider"),
            "provider_symbol": row.get("provider_symbol"),
            "data_frequency": row.get("data_frequency"),
            "unit_label": row.get("unit_label"),
            "collection_status": row.get("collection_status"),
            "readiness": readiness,
            "readiness_reason": reason,
            "data_count": data_count,
            "first_value_date": row.get("first_value_date"),
            "latest_value_date": row.get("value_latest_date") or row.get("latest_value_date"),
            "latest_value": row.get("latest_value"),
            "latest_collected_at": row.get("latest_collected_at"),
            "recommended_minimum_count": signal_min,
            "insufficient_count": max(signal_min - data_count, 0),
            "mapping_ready": mapping_ready,
            "data_ready": data_ready,
            "chart_ready": data_ready,
            "compare_ready": data_ready,
            "signal_ready": signal_ready,
            "supported_transforms": self._supported_transforms_for_readiness(data_count),
        }

    @staticmethod
    def _signal_minimum_rows(frequency: str, indicator_code: str | None = None) -> int:
        code = str(indicator_code or "").upper()
        if code in {"KR_REAL_POLICY_RATE", "US_REAL_POLICY_RATE"}:
            return 60
        if code == "USD_KRW_VOLATILITY":
            return 252
        normalized = frequency.upper()
        if normalized == "MONTHLY":
            return 24
        if normalized == "WEEKLY":
            return 26
        return 60

    @staticmethod
    def _supported_transforms_for_readiness(data_count: int) -> list[str]:
        transforms = ["RAW_VALUE"] if data_count >= 1 else []
        if data_count >= 2:
            transforms.extend(["CHANGE", "CHANGE_RATE", "MOM"])
        if data_count >= 20:
            transforms.extend(["MOVING_AVERAGE", "SLOPE", "TURN_UP", "TURN_DOWN", "DISTANCE_FROM_MA", "CONSECUTIVE_UP", "CONSECUTIVE_DOWN", "PERSISTENCE"])
        if data_count >= 60:
            transforms.extend(["Z_SCORE", "PERCENTILE", "N_PERIOD_HIGH", "N_PERIOD_LOW", "YOY"])
        return transforms

    def _mapping_item(self, row: Any) -> dict[str, Any]:
        item = dict(row)
        item["is_enabled"] = self._as_bool(item.get("is_enabled"))
        item["is_verified"] = self._as_bool(item.get("is_verified"))
        return item
