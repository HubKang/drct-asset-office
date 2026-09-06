from __future__ import annotations

import time
from collections import OrderedDict, defaultdict
from datetime import date
from threading import RLock
from typing import Any

import numpy as np
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.services.drct_pattern_feature_service import FEATURE_SCHEMA_VERSION, PatternFeatureService
from backend.app.services.marker_candidate_policy_research_service import (
    BASELINE_POLICY_VERSION,
    SHADOW_POLICY_VERSION,
)
from backend.app.services.marker_pattern_signature_service import (
    MARKER_PATTERN_SIGNATURE_VERSION,
    PATTERN_SIMILARITY_ALGORITHM_VERSION,
    MarkerPatternSignatureService,
)


MINIMUM_PRIOR_CASE_COUNT = 3
FORMAL_PRIOR_CASE_COUNT = 5
MEANINGFUL_CANDIDATE_REDUCTION_PERCENT = 20.0
HISTORICAL_UNIVERSE_MODE = "CURRENT_ACTIVE_APPROXIMATION"


class MarkerCandidatePolicyValidationService:
    """Runtime-only, past-only replay of baseline and improvement candidate policies."""

    _cache: OrderedDict[tuple[Any, ...], dict[str, Any]] = OrderedDict()
    _cache_lock = RLock()
    _cache_limit = 32

    def __init__(self, db: Session):
        self.db = db
        self.query_count = 0

    def _execute(self, statement: str, params: dict[str, Any] | None = None):
        self.query_count += 1
        return self.db.execute(text(statement), params or {})

    def _universe(self) -> list[dict[str, Any]]:
        rows = self._execute("""
            SELECT DISTINCT stock.id stock_id, stock.stock_code, stock.stock_name
            FROM market_theme_stocks mapping
            JOIN market_themes theme ON theme.id=mapping.theme_id
            JOIN stocks stock ON stock.id=mapping.stock_id
            WHERE COALESCE(mapping.is_active,1)=1 AND theme.is_active=1
              AND COALESCE(theme.theme_level,'THEME')='THEME'
              AND COALESCE(stock.is_active,1)=1
            ORDER BY stock.id
        """).mappings().all()
        return [dict(row) for row in rows]

    def _events(self, marker_id: int, analysis_date: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        rows = self._execute("""
            SELECT marker.id marker_id, marker.name marker_name, marker.symbol marker_symbol,
                   marker_group.id marker_group_id, marker_group.name marker_group,
                   marker_group.color marker_group_color,
                   event.id chart_marker_event_id, event.stock_id, stock.stock_code,
                   stock.stock_name, event.marker_date d0
            FROM chart_markers marker
            JOIN chart_marker_groups marker_group ON marker_group.id=marker.marker_group_id
            JOIN chart_marker_events event ON event.marker_id=marker.id
            JOIN stocks stock ON stock.id=event.stock_id
            LEFT JOIN chart_marker_learning_decisions decision ON decision.chart_marker_event_id=event.id
            WHERE marker.id=:marker_id AND marker.is_active=1 AND marker_group.is_active=1
              AND event.review_result IN ('S','SUCCESS')
              AND event.marker_date<=:analysis_date
              AND COALESCE(decision.decision,'INCLUDE')<>'EXCLUDE'
            ORDER BY event.marker_date, event.id
        """, {"marker_id": marker_id, "analysis_date": analysis_date}).mappings().all()
        if not rows:
            marker = self._execute("""
                SELECT marker.id marker_id, marker.name marker_name, marker.symbol marker_symbol,
                       marker_group.id marker_group_id, marker_group.name marker_group,
                       marker_group.color marker_group_color
                FROM chart_markers marker
                JOIN chart_marker_groups marker_group ON marker_group.id=marker.marker_group_id
                WHERE marker.id=:marker_id AND marker.is_active=1 AND marker_group.is_active=1
            """, {"marker_id": marker_id}).mappings().first()
            if marker is None:
                raise HTTPException(status_code=404, detail="Marker not found")
            return dict(marker), []
        first = rows[0]
        meta = {key: first[key] for key in (
            "marker_id", "marker_name", "marker_symbol", "marker_group_id", "marker_group", "marker_group_color",
        )}
        return meta, [dict(row) for row in rows]

    def _analysis_date(self, stock_ids: list[int], requested: date | None) -> str:
        if requested is not None:
            return requested.isoformat()
        if not stock_ids:
            return ""
        params = {f"analysis_stock_{index}": stock_id for index, stock_id in enumerate(stock_ids)}
        placeholders = ",".join(f":analysis_stock_{index}" for index in range(len(stock_ids)))
        value = self._execute(f"""
            SELECT MIN(latest_trade_date) FROM (
                SELECT stock_id, MAX(trade_date) latest_trade_date
                FROM stock_daily_prices WHERE stock_id IN ({placeholders}) GROUP BY stock_id
            ) completed
        """, params).scalar_one_or_none()
        return str(value)[:10] if value else ""

    def _price_version(self, stock_ids: list[int], analysis_date: str) -> tuple[str, int]:
        if not stock_ids:
            return "", 0
        params: dict[str, Any] = {"analysis_date": analysis_date}
        placeholders = []
        for index, stock_id in enumerate(stock_ids):
            key = f"version_stock_{index}"
            params[key] = stock_id
            placeholders.append(f":{key}")
        row = self._execute(f"""
            SELECT COALESCE(MAX(updated_at),'') latest_update, COUNT(*) row_count
            FROM stock_daily_prices
            WHERE stock_id IN ({','.join(placeholders)}) AND trade_date<=:analysis_date
        """, params).mappings().one()
        return str(row["latest_update"]), int(row["row_count"])

    def _prices(self, stock_ids: list[int], analysis_date: str) -> dict[int, list[dict[str, Any]]]:
        if not stock_ids:
            return {}
        params: dict[str, Any] = {"analysis_date": analysis_date}
        placeholders = []
        for index, stock_id in enumerate(stock_ids):
            key = f"price_stock_{index}"
            params[key] = stock_id
            placeholders.append(f":{key}")
        rows = self._execute(f"""
            SELECT stock_id, trade_date, open_price, high_price, low_price, close_price,
                   volume, trading_value, ma5, ma10, ma20, ma60, ma120, ma240
            FROM stock_daily_prices
            WHERE stock_id IN ({','.join(placeholders)}) AND trade_date<=:analysis_date
            ORDER BY stock_id, trade_date DESC
        """, params).mappings().all()
        grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[int(row["stock_id"])].append(dict(row))
        return grouped

    @staticmethod
    def _core_at(rows_desc: list[dict[str, Any]], d0: str) -> dict[str, float] | None:
        index = next((idx for idx, row in enumerate(rows_desc) if str(row["trade_date"])[:10] == d0), None)
        if index is None:
            return None
        status, features, _missing = PatternFeatureService.core(rows_desc[index:])
        return features if status == "READY" else None

    @staticmethod
    def improvement_status(
        valid_target_count: int,
        baseline_hit_count: int,
        improvement_hit_count: int,
        baseline_average_candidate_count: float | None,
        improvement_average_candidate_count: float | None,
    ) -> str:
        if valid_target_count < 3:
            return "NEED_MORE_DATA"
        if improvement_hit_count < baseline_hit_count:
            return "KEEP_CURRENT"
        if baseline_hit_count < valid_target_count:
            return "VALIDATING"
        if baseline_average_candidate_count is None or improvement_average_candidate_count is None:
            return "VALIDATING"
        reduction = (
            (baseline_average_candidate_count - improvement_average_candidate_count)
            / baseline_average_candidate_count * 100
            if baseline_average_candidate_count > 0 else 0.0
        )
        return "IMPROVEMENT_READY" if reduction >= MEANINGFUL_CANDIDATE_REDUCTION_PERCENT else "VALIDATING"

    @staticmethod
    def _status_message(status: str) -> str:
        return {
            "NEED_MORE_DATA": "과거 성공 사례가 더 쌓이면 현재 방식과 개선안을 자동으로 비교합니다.",
            "VALIDATING": "과거 성공 사례를 이용해 현재 방식과 개선안을 계속 비교하고 있습니다.",
            "IMPROVEMENT_READY": "성공 사례 탐지를 유지하면서 후보 범위를 줄인 개선안을 검토할 수 있습니다.",
            "KEEP_CURRENT": "개선안이 과거 성공 사례 일부를 놓쳐 현재 방식을 유지합니다.",
        }[status]

    @classmethod
    def _get_cached(cls, key: tuple[Any, ...]) -> dict[str, Any] | None:
        with cls._cache_lock:
            result = cls._cache.get(key)
            if result is not None:
                cls._cache.move_to_end(key)
            return result

    @classmethod
    def _put_cached(cls, key: tuple[Any, ...], result: dict[str, Any]) -> None:
        with cls._cache_lock:
            cls._cache[key] = result
            cls._cache.move_to_end(key)
            while len(cls._cache) > cls._cache_limit:
                cls._cache.popitem(last=False)

    def validate(self, marker_id: int, requested_date: date | None = None) -> dict[str, Any]:
        started = time.perf_counter()
        universe = self._universe()
        analysis_date = self._analysis_date([int(row["stock_id"]) for row in universe], requested_date)
        if not analysis_date:
            raise HTTPException(status_code=404, detail="Stock price data not found")
        marker, events = self._events(marker_id, analysis_date)
        stock_ids = sorted({int(row["stock_id"]) for row in universe} | {int(row["stock_id"]) for row in events})
        price_version = self._price_version(stock_ids, analysis_date)
        event_version = tuple((int(row["chart_marker_event_id"]), int(row["stock_id"]), str(row["d0"])[:10]) for row in events)
        cache_key = (
            self.db.get_bind(), marker_id, analysis_date, FEATURE_SCHEMA_VERSION,
            MARKER_PATTERN_SIGNATURE_VERSION, PATTERN_SIMILARITY_ALGORITHM_VERSION,
            tuple(int(row["stock_id"]) for row in universe), event_version, price_version,
        )
        cached = self._get_cached(cache_key)
        if cached is not None:
            return {**cached, "timings": {**cached["timings"], "total_ms": int((time.perf_counter() - started) * 1000),
                                           "sql_query_count": self.query_count, "cache_hit": True}}

        prices = self._prices(stock_ids, analysis_date)
        cases = []
        for event in events:
            d0 = str(event["d0"])[:10]
            features = self._core_at(prices.get(int(event["stock_id"]), []), d0)
            if features is not None:
                cases.append({
                    "chart_marker_event_id": int(event["chart_marker_event_id"]),
                    "stock_id": int(event["stock_id"]), "stock_code": str(event["stock_code"]),
                    "stock_name": str(event["stock_name"]), "d0": d0, "review_result": "S",
                    "learning_decision": None, "core_status": "READY", "core_features": features,
                })

        universe_ids = {int(row["stock_id"]) for row in universe}
        targets = []
        for target in cases:
            prior = [case for case in cases if str(case["d0"]) < str(target["d0"])]
            if len(prior) < MINIMUM_PRIOR_CASE_COUNT:
                continue
            signature = MarkerPatternSignatureService.build_signature(prior, "CORE")
            prior_validation = MarkerPatternSignatureService.validate(prior, "CORE")
            distribution = prior_validation.get("distribution")
            target_score = MarkerPatternSignatureService.score(target["core_features"], signature)
            if distribution is None or target_score is None:
                continue

            current_scores = []
            for stock in universe:
                features = self._core_at(prices.get(int(stock["stock_id"]), []), str(target["d0"]))
                if features is None:
                    continue
                score = MarkerPatternSignatureService.score(features, signature)
                if score is not None:
                    current_scores.append(float(score["pattern_similarity"]))
            if not current_scores:
                continue
            baseline_threshold = float(distribution["p25"])
            market_threshold = float(np.percentile(np.asarray(current_scores, dtype=float), 90, method="linear"))
            improvement_threshold = max(baseline_threshold, market_threshold)
            target_similarity = float(target_score["pattern_similarity"])
            target_in_universe = int(target["stock_id"]) in universe_ids
            targets.append({
                "chart_marker_event_id": int(target["chart_marker_event_id"]),
                "stock_id": int(target["stock_id"]), "stock_code": str(target["stock_code"]),
                "stock_name": str(target["stock_name"]), "d0": str(target["d0"]),
                "prior_case_count": len(prior), "validation_level": "FORMAL" if len(prior) >= FORMAL_PRIOR_CASE_COUNT else "REFERENCE",
                "target_in_universe": target_in_universe,
                "baseline_hit": target_in_universe and target_similarity >= baseline_threshold,
                "improvement_hit": target_in_universe and target_similarity >= improvement_threshold,
                "baseline_candidate_count": sum(value >= baseline_threshold for value in current_scores),
                "improvement_candidate_count": sum(value >= improvement_threshold for value in current_scores),
            })

        valid_count = len(targets)
        baseline_hits = sum(bool(row["baseline_hit"]) for row in targets)
        improvement_hits = sum(bool(row["improvement_hit"]) for row in targets)
        baseline_average = float(np.mean([row["baseline_candidate_count"] for row in targets])) if targets else None
        improvement_average = float(np.mean([row["improvement_candidate_count"] for row in targets])) if targets else None
        reduction = (
            (baseline_average - improvement_average) / baseline_average * 100
            if baseline_average is not None and improvement_average is not None and baseline_average > 0 else None
        )
        status = self.improvement_status(valid_count, baseline_hits, improvement_hits, baseline_average, improvement_average)
        result = {
            **marker, "analysis_date": analysis_date, "training_s_count": len(cases),
            "historical_valid_target_count": valid_count,
            "formal_target_count": sum(row["validation_level"] == "FORMAL" for row in targets),
            "baseline_hit_count": baseline_hits, "improvement_hit_count": improvement_hits,
            "baseline_average_candidate_count": baseline_average,
            "improvement_average_candidate_count": improvement_average,
            "candidate_reduction_percent": reduction,
            "automatic_improvement_status": status, "status_message": self._status_message(status),
            "baseline_policy_version": BASELINE_POLICY_VERSION, "improvement_policy_version": SHADOW_POLICY_VERSION,
            "minimum_prior_case_count": MINIMUM_PRIOR_CASE_COUNT, "formal_prior_case_count": FORMAL_PRIOR_CASE_COUNT,
            "historical_universe_mode": HISTORICAL_UNIVERSE_MODE,
            "historical_universe_notice": "과거 테마 구성까지 완전히 복원한 Backtest는 아니며, 현재 활성 연결종목을 각 과거 시점 가격으로 평가합니다.",
            "targets": targets,
            "timings": {"total_ms": int((time.perf_counter() - started) * 1000),
                        "sql_query_count": self.query_count, "evaluated_target_count": valid_count, "cache_hit": False},
            "storage_policy": "RUNTIME_ONLY",
        }
        self._put_cached(cache_key, result)
        return result
