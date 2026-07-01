from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.providers.economic_data.bok_ecos_provider import BokEcosProvider

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
        mapping = self._get_mapping(indicator["indicator_code"], "BOK_ECOS")
        result = self.bok_ecos.test_mapping(mapping, start_date=getattr(payload, "start_date", None), end_date=getattr(payload, "end_date", None))
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
                    WHERE indicator_code = :indicator_code AND provider = 'BOK_ECOS'
                    """
                ),
                {"indicator_code": indicator["indicator_code"], "is_verified": 1 if success else 0, "status": status_value, "message": message},
            )
            self.db.commit()
        rows = result.get("rows") or []
        return {
            "indicator_code": indicator["indicator_code"],
            "provider": "BOK_ECOS",
            "status": status_value,
            "message": message,
            "sample_count": len(rows),
            "sample_rows": rows[:5],
        }

    def activate_provider_mapping(self, indicator_code: str) -> dict[str, Any]:
        indicator = self.get_indicator(indicator_code)
        mapping = self._get_mapping(indicator["indicator_code"], "BOK_ECOS")
        if not mapping.get("is_verified"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="provider mapping must be tested successfully before activation")
        self.db.execute(
            text(
                """
                UPDATE market_indicator_provider_mappings
                SET is_enabled = 1, updated_at = CURRENT_TIMESTAMP
                WHERE indicator_code = :indicator_code AND provider = 'BOK_ECOS'
                """
            ),
            {"indicator_code": indicator["indicator_code"]},
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
        return self._get_mapping(indicator["indicator_code"], "BOK_ECOS")

    def collect_indicator(self, indicator_codes: list[str] | None = None, *, start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
        targets = self._collection_targets(indicator_codes)
        date_to = end_date or date.today().isoformat()
        date_from = start_date or (date.today() - timedelta(days=370)).isoformat()
        results: list[dict[str, Any]] = []
        success_count = 0
        waiting_count = 0
        failed_count = 0
        for code in targets:
            try:
                mapping = self._get_enabled_mapping(code)
                if not mapping:
                    waiting_count += 1
                    results.append({"indicator_code": code, "status": "WAITING", "message": "enabled and verified BOK_ECOS mapping is required", "saved_count": 0})
                    continue
                values = self.bok_ecos.collect_values(code, mapping, start_date=date_from, end_date=date_to)
                if not values:
                    waiting_count += 1
                    self._mark_indicator_status(code, "WAITING")
                    results.append({"indicator_code": code, "status": "WAITING", "message": "BOK ECOS returned no collectable rows", "saved_count": 0})
                    continue
                for value in values:
                    self._upsert_value(value)
                latest = values[-1]
                self._update_indicator_latest(code, latest)
                success_count += 1
                results.append(
                    {
                        "indicator_code": code,
                        "status": "SUCCESS",
                        "message": f"saved {len(values)} BOK ECOS rows",
                        "saved_count": len(values),
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
            "failed_count": failed_count,
            "message": f"BOK ECOS collection completed: success {success_count}, waiting {waiting_count}, failed {failed_count}.",
            "results": results,
        }

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
                WHERE is_active = 1 AND category IN ('FX', 'RATE')
                ORDER BY display_order
                """
            )
        ).mappings().all()
        return [str(row["indicator_code"]) for row in rows]

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
                  AND m.provider = 'BOK_ECOS'
                  AND m.is_enabled = 1
                  AND m.is_verified = 1
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

    def _mapping_item(self, row: Any) -> dict[str, Any]:
        item = dict(row)
        item["is_enabled"] = self._as_bool(item.get("is_enabled"))
        item["is_verified"] = self._as_bool(item.get("is_verified"))
        return item