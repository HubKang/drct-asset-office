from __future__ import annotations

import statistics
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.services.drct_future_outcome_service import FutureOutcomeService
from backend.app.services.drct_pattern_feature_service import FEATURE_SCHEMA_VERSION, PatternFeatureService
from backend.app.services.marker_review_result import normalize_marker_review_result


@dataclass
class MarkerDatasetBuild:
    marker: dict[str, Any]
    cases: list[dict[str, Any]]
    related_search_count: int
    elapsed_ms: int


class MarkerTrainingCaseService:
    """Build marker datasets from marker_id alone; search rules are not dependencies."""

    def __init__(self, db: Session):
        self.db = db

    def catalog(self) -> dict[str, Any]:
        rows = self.db.execute(text("""
            SELECT marker.id marker_id, marker.name marker_name, marker.symbol marker_symbol,
                   marker.marker_group_id, marker_group.name marker_group_name,
                   marker_group.color marker_group_color,
                   COUNT(event.id) event_count,
                   SUM(CASE WHEN event.review_result IN ('S','SUCCESS') THEN 1 ELSE 0 END) s_count,
                   SUM(CASE WHEN event.review_result IN ('F','FAILURE') THEN 1 ELSE 0 END) f_count,
                   SUM(CASE WHEN event.id IS NOT NULL AND event.review_result IS NULL THEN 1 ELSE 0 END) undecided_count
            FROM chart_markers marker
            JOIN chart_marker_groups marker_group ON marker_group.id=marker.marker_group_id
            LEFT JOIN chart_marker_events event ON event.marker_id=marker.id
            WHERE marker.is_active=1 AND marker_group.is_active=1
            GROUP BY marker.id
            ORDER BY marker_group.sort_order, marker_group.name, marker.sort_order, marker.name
        """)).mappings().all()
        return {"items": [self._marker(dict(row)) for row in rows]}

    @staticmethod
    def _marker(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "marker_id": int(row["marker_id"]), "marker_name": str(row["marker_name"]),
            "marker_symbol": str(row["marker_symbol"]), "marker_group_id": int(row["marker_group_id"]),
            "marker_group_name": str(row["marker_group_name"]), "marker_group_color": str(row["marker_group_color"]),
            "event_count": int(row.get("event_count") or 0), "s_count": int(row.get("s_count") or 0),
            "f_count": int(row.get("f_count") or 0), "undecided_count": int(row.get("undecided_count") or 0),
        }

    def _marker_and_events(self, marker_id: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        marker = self.db.execute(text("""
            SELECT marker.id marker_id, marker.name marker_name, marker.symbol marker_symbol,
                   marker.marker_group_id, marker_group.name marker_group_name,
                   marker_group.color marker_group_color
            FROM chart_markers marker
            JOIN chart_marker_groups marker_group ON marker_group.id=marker.marker_group_id
            WHERE marker.id=:marker_id
        """), {"marker_id": marker_id}).mappings().first()
        if marker is None:
            raise HTTPException(404, "차트마커를 찾을 수 없습니다.")
        events = self.db.execute(text("""
            SELECT event.id chart_marker_event_id, event.marker_id, event.stock_id,
                   event.marker_date d0, event.review_result, stock.stock_code, stock.stock_name,
                   decision.decision learning_decision, decision.decision_reason,
                   decision.updated_at decision_updated_at
            FROM chart_marker_events event
            JOIN stocks stock ON stock.id=event.stock_id
            LEFT JOIN chart_marker_learning_decisions decision ON decision.chart_marker_event_id=event.id
            WHERE event.marker_id=:marker_id
            ORDER BY event.marker_date, event.stock_id, event.id
        """), {"marker_id": marker_id}).mappings().all()
        counts = {"event_count": len(events), "s_count": 0, "f_count": 0, "undecided_count": 0}
        normalized_events = []
        for raw in events:
            event = dict(raw)
            event["review_result"] = normalize_marker_review_result(event["review_result"])
            counts[{"S": "s_count", "F": "f_count", None: "undecided_count"}[event["review_result"]]] += 1
            normalized_events.append(event)
        return self._marker({**dict(marker), **counts}), normalized_events

    def _prices(self, stock_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
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

    def _indicators(self, stock_ids: list[int]) -> dict[tuple[int, str], dict[str, Any]]:
        if not stock_ids: return {}
        params = {f"indicator_{index}": stock_id for index, stock_id in enumerate(stock_ids)}
        placeholders = ",".join(f":indicator_{index}" for index in range(len(stock_ids)))
        rows = self.db.execute(text(f"""
            SELECT stock_id, trade_date, rsi14, macd_histogram, bb_width, atr14_ratio_to_close
            FROM stock_daily_technical_indicators WHERE stock_id IN ({placeholders})
        """), params).mappings().all()
        return {(int(row["stock_id"]), str(row["trade_date"])[:10]): dict(row) for row in rows}

    def _related_search_count(self, marker_id: int) -> int:
        return int(self.db.execute(text("""
            SELECT COUNT(DISTINCT search_id) FROM drct_signal_search_marker_links
            WHERE marker_definition_id=:marker_id
        """), {"marker_id": marker_id}).scalar_one())

    def build(self, marker_id: int) -> MarkerDatasetBuild:
        started = time.perf_counter()
        marker, events = self._marker_and_events(marker_id)
        stock_ids = sorted({int(event["stock_id"]) for event in events})
        price_by_stock = self._prices(stock_ids)
        indicators = self._indicators(stock_ids)
        cases = self._cases_from_events(marker, events, price_by_stock, indicators)
        return MarkerDatasetBuild(marker, cases, self._related_search_count(marker_id), int((time.perf_counter() - started) * 1000))

    @staticmethod
    def _cases_from_events(
        marker: dict[str, Any],
        events: list[dict[str, Any]],
        price_by_stock: dict[int, list[dict[str, Any]]],
        indicators: dict[tuple[int, str], dict[str, Any]],
    ) -> list[dict[str, Any]]:
        cases = []
        for event in events:
            d0 = str(event["d0"])[:10]
            all_rows = price_by_stock.get(int(event["stock_id"]), [])
            d0_index = next((index for index, row in enumerate(all_rows) if str(row["trade_date"])[:10] == d0), None)
            rows_desc = list(reversed(all_rows[:d0_index + 1])) if d0_index is not None else []
            core_status, core_features, core_missing = PatternFeatureService.core(rows_desc)
            d0_row = rows_desc[0] if rows_desc else None
            d0_close = float(d0_row["close_price"]) if d0_row and d0_row.get("close_price") is not None else None
            enriched_status, enriched_features, enriched_missing = PatternFeatureService.enriched(
                core_features, indicators.get((int(event["stock_id"]), d0)), d0_close
            )
            future_rows = all_rows[d0_index + 1:d0_index + 21] if d0_index is not None else []
            cases.append({
                **event, "marker_name": marker["marker_name"], "d0": d0,
                "d0_price_ready": d0_row is not None and d0_close is not None,
                "d0_price": {key: d0_row.get(key) for key in ("open_price", "high_price", "low_price", "close_price", "volume", "trading_value", "ma5", "ma10", "ma20", "ma60", "ma120", "ma240")} if d0_row else None,
                "core_status": core_status, "enriched_status": enriched_status,
                "core_features": core_features, "enriched_features": enriched_features,
                "core_missing": core_missing, "enriched_missing": enriched_missing,
                "outcomes": FutureOutcomeService.calculate(d0_close, future_rows),
            })
        return cases

    @staticmethod
    def summary(build: MarkerDatasetBuild) -> dict[str, Any]:
        cases = build.cases
        core_ready = [case for case in cases if case["core_status"] == "READY"]
        quality = [case for case in core_ready if case["review_result"] in {"S", "F"}]
        return {
            "total_event_count": len(cases),
            "d0_price_ready_count": sum(case["d0_price_ready"] for case in cases),
            "core_ready_count": len(core_ready),
            "enriched_ready_count": sum(case["enriched_status"] == "READY" for case in cases),
            "pattern_case_count": len(core_ready), "quality_case_count": len(quality),
            "review_counts": {"S": sum(case["review_result"] == "S" for case in cases), "F": sum(case["review_result"] == "F" for case in cases), "undecided": sum(case["review_result"] is None for case in cases)},
            "outcome_coverage": {key: sum(case["outcomes"].get(key) is not None for case in cases) for key in ("d5_return", "d10_return", "d20_return", "mfe_20", "mae_20")},
            "related_search_count": build.related_search_count,
            "latest_d0": max((case["d0"] for case in cases), default=None),
            "feature_schema_version": FEATURE_SCHEMA_VERSION, "elapsed_ms": build.elapsed_ms,
        }

    def readiness(self, marker_id: int) -> dict[str, Any]:
        build = self.build(marker_id)
        return {"marker": build.marker, "summary": self.summary(build)}

    @staticmethod
    def _case_item(case: dict[str, Any]) -> dict[str, Any]:
        return {
            "chart_marker_event_id": case["chart_marker_event_id"], "marker_id": case["marker_id"],
            "marker_name": case["marker_name"], "stock_id": case["stock_id"], "stock_code": case["stock_code"],
            "stock_name": case["stock_name"], "d0": case["d0"], "review_result": case["review_result"],
            "d0_price_ready": case["d0_price_ready"], "core_status": case["core_status"], "enriched_status": case["enriched_status"],
            "d20_return": case["outcomes"]["d20_return"], "mfe_20": case["outcomes"]["mfe_20"], "mae_20": case["outcomes"]["mae_20"],
            "learning_decision": case.get("learning_decision"),
        }

    def cases(self, marker_id: int, review_result: str, page: int, page_size: int) -> dict[str, Any]:
        build = self.build(marker_id)
        selected = build.cases
        if review_result == "UNDECIDED": selected = [case for case in selected if case["review_result"] is None]
        elif review_result in {"S", "F"}: selected = [case for case in selected if case["review_result"] == review_result]
        total = len(selected); start = (page - 1) * page_size
        return {"marker_id": marker_id, "page": page, "page_size": page_size, "total": total,
                "items": [self._case_item(case) for case in selected[start:start + page_size]], "elapsed_ms": build.elapsed_ms}

    def case_detail(self, marker_id: int, event_id: int) -> dict[str, Any]:
        build = self.build(marker_id)
        case = next((case for case in build.cases if int(case["chart_marker_event_id"]) == event_id), None)
        if case is None: raise HTTPException(404, "Marker 사례를 찾을 수 없습니다.")
        return {**self._case_item(case), "feature_schema_version": FEATURE_SCHEMA_VERSION,
                "d0_price": case["d0_price"], "core_features": case["core_features"], "enriched_features": case["enriched_features"],
                "core_missing": case["core_missing"], "enriched_missing": case["enriched_missing"], "outcomes": case["outcomes"],
                "outcome_notice": "Outcome은 Marker D0 이후 시장 결과이며 Feature에 포함되지 않습니다."}

    @staticmethod
    def _metrics(cases: list[dict[str, Any]]) -> dict[str, dict[str, float | int | None]]:
        result = {}
        for key in ("d5_return", "d10_return", "d20_return", "mfe_20", "mae_20"):
            values = [float(case["outcomes"][key]) for case in cases if case["outcomes"].get(key) is not None]
            result[key] = {"mean": sum(values) / len(values) if values else None, "median": statistics.median(values) if values else None, "n": len(values)}
        return result

    def outcomes(self, marker_id: int) -> dict[str, Any]:
        build = self.build(marker_id)
        eligible = [case for case in build.cases if case["core_status"] == "READY" and case["review_result"] in {"S", "F"}]
        s_cases = [case for case in eligible if case["review_result"] == "S"]
        f_cases = [case for case in eligible if case["review_result"] == "F"]
        s_metrics, f_metrics = self._metrics(s_cases), self._metrics(f_cases)
        difference = {key: None if s_metrics[key]["mean"] is None or f_metrics[key]["mean"] is None else float(s_metrics[key]["mean"]) - float(f_metrics[key]["mean"]) for key in s_metrics}
        return {"marker_id": marker_id, "quality_case_count": len(eligible), "labels": {"S": len(s_cases), "F": len(f_cases)},
                "outcomes": {"S": s_metrics, "F": f_metrics}, "difference": difference, "elapsed_ms": build.elapsed_ms}

    def related_searches(self, marker_id: int) -> dict[str, Any]:
        self._marker_and_events(marker_id)
        rows = self.db.execute(text("""
            SELECT search.id search_id, search.name search_name, search.lifecycle_status, search.is_active,
                   version.version_no current_version_no, COALESCE(rule.validation_status, 'NOT_CONFIGURED') rule_status
            FROM drct_signal_search_marker_links link
            JOIN drct_signal_searches search ON search.id=link.search_id
            JOIN drct_signal_search_versions version ON version.search_id=search.id AND version.is_current=1
            LEFT JOIN drct_signal_search_rules rule ON rule.search_version_id=version.id
            WHERE link.marker_definition_id=:marker_id ORDER BY search.display_order, search.name
        """), {"marker_id": marker_id}).mappings().all()
        return {"marker_id": marker_id, "items": [dict(row) for row in rows],
                "notice": "관련 검색식은 Marker 학습의 필수조건이 아니며 향후 알고리즘 개선을 위한 참고 데이터입니다."}
