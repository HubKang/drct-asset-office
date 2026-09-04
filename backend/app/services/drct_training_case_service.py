from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.services.drct_future_outcome_service import FutureOutcomeService
from backend.app.services.drct_pattern_feature_service import FEATURE_SCHEMA_VERSION, PatternFeatureService
from backend.app.services.drct_rule_engine import DrctRuleEvaluator, DrctRuleValidator
from backend.app.services.marker_review_result import legacy_training_label


@dataclass
class TrainingDatasetBuild:
    search_id: int
    search_version_id: int
    version_no: int
    rule_status: str
    rule_schema_version: int | None
    marker_link_count: int
    cases: list[dict[str, Any]]
    summary: dict[str, Any]
    elapsed_ms: int


class TrainingCaseService:
    def __init__(self, db: Session):
        self.db = db

    def _version_rule(self, search_id: int, search_version_id: int | None) -> tuple[dict[str, Any], dict[str, Any] | None, str]:
        params: dict[str, Any] = {"search_id": search_id}
        where = "version.search_id=:search_id"
        if search_version_id is None:
            where += " AND version.is_current=1"
        else:
            where += " AND version.id=:version_id"
            params["version_id"] = search_version_id
        row = self.db.execute(text(f"""
            SELECT version.id, version.version_no, rule.rule_json, rule.validation_status
            FROM drct_signal_search_versions version
            JOIN drct_signal_searches search ON search.id=version.search_id
            LEFT JOIN drct_signal_search_rules rule ON rule.search_version_id=version.id
            WHERE {where}
        """), params).mappings().first()
        if row is None:
            raise HTTPException(404, "검색식 Version을 찾을 수 없습니다.")
        if row["rule_json"] is None:
            return dict(row), None, "RULE_NOT_CONFIGURED"
        rule = json.loads(str(row["rule_json"]))
        validation = DrctRuleValidator.validate(rule)
        if validation.status != "VALID" or row["validation_status"] != "VALID":
            return dict(row), rule, "RULE_INVALID"
        return dict(row), rule, "VALID"

    def _linked_rows(self, search_id: int) -> tuple[int, list[dict[str, Any]]]:
        rows = self.db.execute(text("""
            SELECT link.marker_definition_id, marker.name AS marker_name,
                   event.id AS event_id, event.stock_id, event.marker_date, event.review_result,
                   stock.stock_code, stock.stock_name
            FROM drct_signal_search_marker_links link
            JOIN chart_markers marker ON marker.id=link.marker_definition_id
            LEFT JOIN chart_marker_events event ON event.marker_id=link.marker_definition_id
            LEFT JOIN stocks stock ON stock.id=event.stock_id
            WHERE link.search_id=:search_id
            ORDER BY event.marker_date, event.stock_id, event.id
        """), {"search_id": search_id}).mappings().all()
        marker_count = len({int(row["marker_definition_id"]) for row in rows})
        return marker_count, [dict(row) for row in rows if row["event_id"] is not None]

    @staticmethod
    def _deduplicate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[(int(row["stock_id"]), str(row["marker_date"])[:10])].append(row)
        cases = []
        for (stock_id, marker_date), events in grouped.items():
            labels = {label for row in events if (label := legacy_training_label(row["review_result"])) is not None}
            if labels == {"SUCCESS", "FAILURE"}: label = "CONFLICT"
            elif "SUCCESS" in labels: label = "SUCCESS"
            elif "FAILURE" in labels: label = "FAILURE"
            else: label = "UNDECIDED"
            cases.append({
                "stock_id": stock_id, "stock_code": str(events[0]["stock_code"]), "stock_name": str(events[0]["stock_name"]),
                "d0": marker_date, "label": label,
                "source_marker_event_ids": [int(row["event_id"]) for row in events],
                "matched_marker_names": list(dict.fromkeys(str(row["marker_name"]) for row in events)),
            })
        return sorted(cases, key=lambda item: (item["d0"], item["stock_id"]))

    def _bulk_prices(self, stock_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
        if not stock_ids: return {}
        params = {f"stock_{index}": stock_id for index, stock_id in enumerate(stock_ids)}
        placeholders = ",".join(f":stock_{index}" for index in range(len(stock_ids)))
        rows = self.db.execute(text(f"""
            SELECT stock_id, trade_date, open_price, high_price, low_price, close_price,
                   volume, trading_value, ma5, ma10, ma20, ma60, ma120, ma240
            FROM stock_daily_prices WHERE stock_id IN ({placeholders})
            ORDER BY stock_id, trade_date
        """), params).mappings().all()
        grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in rows: grouped[int(row["stock_id"])].append(dict(row))
        return grouped

    def _bulk_indicators(self, stock_ids: list[int]) -> dict[tuple[int, str], dict[str, Any]]:
        if not stock_ids: return {}
        params = {f"indicator_stock_{index}": stock_id for index, stock_id in enumerate(stock_ids)}
        placeholders = ",".join(f":indicator_stock_{index}" for index in range(len(stock_ids)))
        rows = self.db.execute(text(f"""
            SELECT stock_id, trade_date, rsi14, macd, macd_signal, macd_histogram,
                   bb_width, bb_close_position, atr14_ratio_to_close,
                   ma5_gap_pct, ma10_gap_pct, ma20_gap_pct, ma60_gap_pct,
                   ma120_gap_pct, ma240_gap_pct, volume_5_20_ratio
            FROM stock_daily_technical_indicators
            WHERE stock_id IN ({placeholders})
        """), params).mappings().all()
        return {(int(row["stock_id"]), str(row["trade_date"])[:10]): dict(row) for row in rows}

    def _bulk_market_caps(self, stock_ids: list[int]) -> dict[tuple[int, str], int]:
        if not stock_ids: return {}
        params = {f"cap_stock_{index}": stock_id for index, stock_id in enumerate(stock_ids)}
        placeholders = ",".join(f":cap_stock_{index}" for index in range(len(stock_ids)))
        rows = self.db.execute(text(f"""
            WITH ranked AS (
                SELECT stock_id, trade_date, market_cap,
                       ROW_NUMBER() OVER (PARTITION BY stock_id, trade_date ORDER BY updated_at DESC, id DESC) rn
                FROM stock_daily_market_metrics
                WHERE stock_id IN ({placeholders}) AND market_cap IS NOT NULL
            )
            SELECT stock_id, trade_date, market_cap FROM ranked WHERE rn=1
        """), params).mappings().all()
        return {(int(row["stock_id"]), str(row["trade_date"])[:10]): int(row["market_cap"]) for row in rows}

    @staticmethod
    def _outcome_summary(cases: list[dict[str, Any]], label: str) -> dict[str, Any]:
        selected = [case for case in cases if case["label"] == label and case["rule_status"] == "RULE_MATCH"]
        result: dict[str, Any] = {"case_count": len(selected)}
        for key in ("d5_return", "d10_return", "d20_return", "mfe_20", "mae_20"):
            values = [float(case["outcomes"][key]) for case in selected if case["outcomes"].get(key) is not None]
            result[key] = sum(values) / len(values) if values else None
            result[f"{key}_coverage"] = len(values)
        return result

    @classmethod
    def _summary(cls, linked_event_count: int, reviewed_event_count: int, cases: list[dict[str, Any]], marker_link_count: int, rule_status: str) -> dict[str, Any]:
        rule_evaluable = sum(case["rule_status"] in {"RULE_MATCH", "RULE_NO_MATCH"} for case in cases)
        rule_matched = sum(case["rule_status"] == "RULE_MATCH" for case in cases)
        eligible = [case for case in cases if case["label"] in {"SUCCESS", "FAILURE"} and case["rule_status"] == "RULE_MATCH"]
        core_ready = sum(case["core_status"] == "READY" for case in eligible)
        enriched_ready = sum(case["enriched_status"] == "READY" for case in eligible)
        blockers = []
        if rule_status != "VALID": blockers.append(rule_status)
        if marker_link_count == 0: blockers.append("NO_MARKER_LINK")
        return {
            "readiness_status": blockers[0] if blockers else "DATASET_READY",
            "blocking_reasons": blockers,
            "marker_link_count": marker_link_count,
            "linked_event_count": linked_event_count,
            "reviewed_event_count": reviewed_event_count,
            "dedup_case_count": len(cases),
            "label_conflict_count": sum(case["label"] == "CONFLICT" for case in cases),
            "undecided_count": sum(case["label"] == "UNDECIDED" for case in cases),
            "rule_evaluable_count": rule_evaluable,
            "rule_matched_count": rule_matched,
            "rule_no_match_count": sum(case["rule_status"] == "RULE_NO_MATCH" for case in cases),
            "rule_data_incomplete_count": sum(case["rule_status"] == "RULE_DATA_INCOMPLETE" for case in cases),
            "rule_match_rate": rule_matched / rule_evaluable * 100 if rule_evaluable else None,
            "core_ready_count": core_ready,
            "enriched_ready_count": enriched_ready,
            "core_data_incomplete_count": sum(case["core_status"] != "READY" for case in eligible),
            "enriched_data_incomplete_count": sum(case["enriched_status"] != "READY" for case in eligible),
            "success_count": sum(case["label"] == "SUCCESS" and case["rule_status"] == "RULE_MATCH" for case in cases),
            "failure_count": sum(case["label"] == "FAILURE" and case["rule_status"] == "RULE_MATCH" for case in cases),
            "latest_d0": max((case["d0"] for case in cases), default=None),
            "outcome_coverage": {key: sum(case["outcomes"].get(key) is not None for case in eligible) for key in ("d5_return", "d10_return", "d20_return", "mfe_20", "mae_20")},
            "outcome_by_label": {"SUCCESS": cls._outcome_summary(cases, "SUCCESS"), "FAILURE": cls._outcome_summary(cases, "FAILURE")},
        }

    def build(self, search_id: int, search_version_id: int | None = None) -> TrainingDatasetBuild:
        started = time.perf_counter()
        version, rule, rule_status = self._version_rule(search_id, search_version_id)
        marker_link_count, event_rows = self._linked_rows(search_id)
        cases = self._deduplicate(event_rows)
        if rule_status == "VALID" and marker_link_count > 0 and cases:
            stock_ids = sorted({case["stock_id"] for case in cases})
            price_by_stock = self._bulk_prices(stock_ids)
            indicators = self._bulk_indicators(stock_ids)
            market_caps = self._bulk_market_caps(stock_ids)
            validation = DrctRuleValidator.validate(rule or {})
            for case in cases:
                all_rows = price_by_stock.get(case["stock_id"], [])
                d0_index = next((index for index, row in enumerate(all_rows) if str(row["trade_date"])[:10] == case["d0"]), None)
                if d0_index is None:
                    rows_desc: list[dict[str, Any]] = []
                    case["rule_status"] = "RULE_DATA_INCOMPLETE"
                    case["rule_diagnostics"] = []
                else:
                    rows_desc = list(reversed(all_rows[:d0_index + 1]))
                    if len(rows_desc) < validation.required_lookback + 1:
                        evaluated = {"status": "DATA_INCOMPLETE", "conditions": []}
                    else:
                        evaluated = DrctRuleEvaluator.evaluate(rule or {}, rows_desc, market_caps.get((case["stock_id"], case["d0"])))
                    case["rule_status"] = {"MATCH": "RULE_MATCH", "NO_MATCH": "RULE_NO_MATCH", "DATA_INCOMPLETE": "RULE_DATA_INCOMPLETE"}[evaluated["status"]]
                    case["rule_diagnostics"] = evaluated["conditions"]
                core_status, core_features, core_missing = PatternFeatureService.core(rows_desc)
                d0_close = float(rows_desc[0]["close_price"]) if rows_desc and rows_desc[0].get("close_price") is not None else None
                enriched_status, enriched_features, enriched_missing = PatternFeatureService.enriched(core_features, indicators.get((case["stock_id"], case["d0"])), d0_close)
                future_rows = all_rows[d0_index + 1:d0_index + 21] if d0_index is not None else []
                case.update({
                    "core_status": core_status, "enriched_status": enriched_status,
                    "core_features": core_features, "enriched_features": enriched_features,
                    "core_missing": core_missing, "enriched_missing": enriched_missing,
                    "outcomes": FutureOutcomeService.calculate(d0_close, future_rows),
                })
        else:
            case_rule_status = rule_status if rule_status != "VALID" else "RULE_NOT_EVALUATED"
            for case in cases:
                case.update({"rule_status": case_rule_status, "rule_diagnostics": [], "core_status": "NOT_EVALUATED", "enriched_status": "NOT_EVALUATED", "core_features": None, "enriched_features": None, "core_missing": [], "enriched_missing": [], "outcomes": FutureOutcomeService.calculate(None, [])})
        reviewed_event_count = sum(legacy_training_label(row["review_result"]) is not None for row in event_rows)
        summary = self._summary(len(event_rows), reviewed_event_count, cases, marker_link_count, rule_status)
        rule_schema_version = int(rule.get("schema_version", 1)) if rule is not None else None
        return TrainingDatasetBuild(search_id, int(version["id"]), int(version["version_no"]), rule_status, rule_schema_version, marker_link_count, cases, summary, int((time.perf_counter() - started) * 1000))


DRCT_PATTERN_FEATURE_SCHEMA_V1 = FEATURE_SCHEMA_VERSION
