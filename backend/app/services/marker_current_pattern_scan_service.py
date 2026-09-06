from __future__ import annotations

import logging
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
from backend.app.services.marker_pattern_signature_service import (
    MARKER_PATTERN_SIGNATURE_VERSION,
    PATTERN_SIMILARITY_ALGORITHM_VERSION,
    MarkerPatternSignatureService,
)
from backend.app.services.marker_candidate_policy_research_service import (
    BASELINE_POLICY_VERSION,
    SHADOW_POLICY_VERSION,
    MarkerCandidatePolicyResearchService,
)


CANDIDATE_POLICY_VERSION = 1
BAND_RANK = {"VERY_SIMILAR": 0, "HIGH_SIMILARITY": 1, "SIMILAR": 2}
logger = logging.getLogger(__name__)


class MarkerCurrentPatternScanService:
    """Read-only S-only current-pattern scan with a fixed number of bulk queries."""

    _signature_cache: OrderedDict[tuple[Any, ...], dict[int, dict[str, Any]]] = OrderedDict()
    _signature_cache_lock = RLock()
    _signature_cache_limit = 16

    def __init__(self, db: Session):
        self.db = db
        self.query_count = 0

    def _execute(self, statement: str, params: dict[str, Any] | None = None):
        self.query_count += 1
        return self.db.execute(text(statement), params or {})

    def _universe(self) -> list[dict[str, Any]]:
        rows = self._execute("""
            SELECT stock.id stock_id, stock.stock_code, stock.stock_name, theme.theme_name
            FROM market_theme_stocks mapping
            JOIN market_themes theme ON theme.id=mapping.theme_id
            JOIN stocks stock ON stock.id=mapping.stock_id
            WHERE COALESCE(mapping.is_active,1)=1 AND theme.is_active=1
              AND COALESCE(theme.theme_level,'THEME')='THEME'
              AND COALESCE(stock.is_active,1)=1
            ORDER BY stock.id, theme.sort_order, theme.theme_name
        """).mappings().all()
        by_stock: dict[int, dict[str, Any]] = {}
        for row in rows:
            stock_id = int(row["stock_id"])
            stock = by_stock.setdefault(stock_id, {
                "stock_id": stock_id, "stock_code": str(row["stock_code"]),
                "stock_name": str(row["stock_name"]), "theme_names": [],
            })
            theme_name = str(row["theme_name"])
            if theme_name not in stock["theme_names"]:
                stock["theme_names"].append(theme_name)
        return list(by_stock.values())

    def _analysis_date(self, stock_ids: list[int], requested: date | None) -> str | None:
        if requested is not None:
            return requested.isoformat()
        if not stock_ids:
            return None
        params = {f"stock_{index}": stock_id for index, stock_id in enumerate(stock_ids)}
        placeholders = ",".join(f":stock_{index}" for index in range(len(stock_ids)))
        value = self._execute(f"""
            SELECT MIN(latest_trade_date) FROM (
                SELECT stock_id, MAX(trade_date) latest_trade_date
                FROM stock_daily_prices WHERE stock_id IN ({placeholders}) GROUP BY stock_id
            ) completed
        """, params).scalar_one_or_none()
        return str(value)[:10] if value else None

    def _training_events(self, analysis_date: str) -> list[dict[str, Any]]:
        return [dict(row) for row in self._execute("""
            SELECT marker.id marker_id, marker.name marker_name, marker.symbol marker_symbol,
                   marker.marker_group_id, marker_group.name marker_group,
                   marker_group.color marker_group_color,
                   event.id chart_marker_event_id, event.stock_id, event.marker_date d0
            FROM chart_markers marker
            JOIN chart_marker_groups marker_group ON marker_group.id=marker.marker_group_id
            JOIN chart_marker_events event ON event.marker_id=marker.id
            LEFT JOIN chart_marker_learning_decisions decision ON decision.chart_marker_event_id=event.id
            WHERE marker.is_active=1 AND marker_group.is_active=1
              AND event.review_result IN ('S','SUCCESS')
              AND event.marker_date<=:analysis_date
              AND COALESCE(decision.decision,'INCLUDE')<>'EXCLUDE'
            ORDER BY marker_group.sort_order, marker.sort_order, marker.id, event.marker_date, event.id
        """, {"analysis_date": analysis_date}).mappings().all()]

    def _bulk_prices(self, stock_ids: list[int], analysis_date: str) -> dict[int, list[dict[str, Any]]]:
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

    def _bulk_recent_prices(self, stock_ids: list[int], analysis_date: str) -> dict[int, list[dict[str, Any]]]:
        """Load only the 61 candles required by the CORE feature profile."""
        if not stock_ids:
            return {}
        params: dict[str, Any] = {"analysis_date": analysis_date}
        placeholders = []
        for index, stock_id in enumerate(stock_ids):
            key = f"recent_stock_{index}"
            params[key] = stock_id
            placeholders.append(f":{key}")
        rows = self._execute(f"""
            SELECT stock_id, trade_date, open_price, high_price, low_price, close_price,
                   volume, trading_value, ma5, ma10, ma20, ma60, ma120, ma240
            FROM (
                SELECT stock_id, trade_date, open_price, high_price, low_price, close_price,
                       volume, trading_value, ma5, ma10, ma20, ma60, ma120, ma240,
                       ROW_NUMBER() OVER (PARTITION BY stock_id ORDER BY trade_date DESC) row_no
                FROM stock_daily_prices
                WHERE stock_id IN ({','.join(placeholders)}) AND trade_date<=:analysis_date
            ) ranked
            WHERE row_no<=61
            ORDER BY stock_id, trade_date DESC
        """, params).mappings().all()
        grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[int(row["stock_id"])].append(dict(row))
        return grouped

    def _signature_cache_key(self, analysis_date: str, events: list[dict[str, Any]]) -> tuple[Any, ...]:
        event_version = tuple((
            int(row["chart_marker_event_id"]), int(row["marker_id"]), int(row["stock_id"]),
            str(row["d0"])[:10], str(row["marker_name"]), str(row["marker_symbol"]),
            int(row["marker_group_id"]), str(row["marker_group"]), str(row["marker_group_color"]),
        ) for row in events)
        return (
            self.db.get_bind(), analysis_date, FEATURE_SCHEMA_VERSION,
            MARKER_PATTERN_SIGNATURE_VERSION, PATTERN_SIMILARITY_ALGORITHM_VERSION, event_version,
        )

    @classmethod
    def _get_cached_baselines(cls, key: tuple[Any, ...]) -> dict[int, dict[str, Any]] | None:
        with cls._signature_cache_lock:
            cached = cls._signature_cache.get(key)
            if cached is not None:
                cls._signature_cache.move_to_end(key)
            return cached

    @classmethod
    def _put_cached_baselines(cls, key: tuple[Any, ...], value: dict[int, dict[str, Any]]) -> None:
        with cls._signature_cache_lock:
            cls._signature_cache[key] = value
            cls._signature_cache.move_to_end(key)
            while len(cls._signature_cache) > cls._signature_cache_limit:
                cls._signature_cache.popitem(last=False)

    @staticmethod
    def _band(similarity: float, distribution: dict[str, float]) -> str | None:
        if similarity < distribution["p25"]:
            return None
        if similarity >= distribution["p75"]:
            return "VERY_SIMILAR"
        if similarity >= distribution["median"]:
            return "HIGH_SIMILARITY"
        return "SIMILAR"

    @staticmethod
    def _distribution(values: list[float]) -> dict[str, float] | None:
        if not values:
            return None
        data = np.asarray(values, dtype=float)
        percentile = MarkerPatternSignatureService._percentile
        return {
            "min": float(np.min(data)), "p10": percentile(data, 10),
            "p25": percentile(data, 25), "median": float(np.median(data)),
            "p75": percentile(data, 75), "p90": percentile(data, 90),
            "max": float(np.max(data)),
        }

    @staticmethod
    def _core_at(rows_desc: list[dict[str, Any]], d0: str) -> dict[str, float] | None:
        index = next((idx for idx, row in enumerate(rows_desc) if str(row["trade_date"])[:10] == d0), None)
        if index is None:
            return None
        status, features, _missing = PatternFeatureService.core(rows_desc[index:])
        return features if status == "READY" else None

    @staticmethod
    def _empty(analysis_date: str | None, universe_count: int, query_count: int, universe_ms: int, total_ms: int) -> dict[str, Any]:
        return {
            "analysis_date": analysis_date, "universe_count": universe_count,
            "evaluable_stock_count": 0, "incomplete_stock_count": universe_count,
            "eligible_marker_count": 0, "candidate_pair_count": 0, "candidate_stock_count": 0,
            "algorithm": {"feature_schema_version": FEATURE_SCHEMA_VERSION,
                          "pattern_signature_version": MARKER_PATTERN_SIGNATURE_VERSION,
                          "similarity_algorithm_version": PATTERN_SIMILARITY_ALGORITHM_VERSION,
                          "candidate_policy_version": CANDIDATE_POLICY_VERSION},
            "marker_summaries": [], "stocks": [],
            "diagnostics": {"current_policy": "P25", "baseline_policy_version": BASELINE_POLICY_VERSION,
                "shadow_policy": {"candidate_pair_count": 0, "candidate_stock_count": 0, "multiple_marker_stock_count": 0},
                "shadow_policy_status": "VALIDATING", "shadow_policy_version": SHADOW_POLICY_VERSION,
                "markers": [], "policies": {
                key: {"candidate_pair_count": 0, "candidate_stock_count": 0, "multiple_marker_stock_count": 0}
                for key in ("p25", "median", "p75", "p90")
            }, "storage_policy": "RUNTIME_ONLY"},
            "timings": {"universe_ms": universe_ms, "signature_ms": 0, "feature_ms": 0,
                        "similarity_ms": 0, "total_ms": total_ms, "sql_query_count": query_count},
            "storage_policy": "RUNTIME_ONLY",
        }

    def _run(self, requested_date: date | None, include_diagnostics: bool = True) -> tuple[dict[str, Any], dict[tuple[int, int], dict[str, Any]]]:
        total_started = time.perf_counter()
        universe_started = time.perf_counter()
        universe = self._universe()
        analysis_date = self._analysis_date([row["stock_id"] for row in universe], requested_date)
        universe_ms = int((time.perf_counter() - universe_started) * 1000)
        if not analysis_date:
            total_ms = int((time.perf_counter() - total_started) * 1000)
            return self._empty(None, len(universe), self.query_count, universe_ms, total_ms), {}

        signature_started = time.perf_counter()
        events = self._training_events(analysis_date)
        cache_key = self._signature_cache_key(analysis_date, events)
        baselines = self._get_cached_baselines(cache_key)
        if baselines is None:
            all_stock_ids = sorted({row["stock_id"] for row in universe} | {int(row["stock_id"]) for row in events})
            prices = self._bulk_prices(all_stock_ids, analysis_date)
            events_by_marker: dict[int, list[dict[str, Any]]] = defaultdict(list)
            marker_meta: dict[int, dict[str, Any]] = {}
            for event in events:
                marker_id = int(event["marker_id"])
                marker_meta.setdefault(marker_id, {key: event[key] for key in (
                    "marker_id", "marker_name", "marker_symbol", "marker_group_id", "marker_group", "marker_group_color"
                )})
                features = self._core_at(prices.get(int(event["stock_id"]), []), str(event["d0"])[:10])
                if features is not None:
                    events_by_marker[marker_id].append({
                        "chart_marker_event_id": int(event["chart_marker_event_id"]),
                        "stock_id": int(event["stock_id"]), "stock_code": "", "stock_name": "",
                        "d0": str(event["d0"])[:10], "review_result": "S", "learning_decision": None,
                        "core_status": "READY", "core_features": features,
                    })
            baselines = {}
            for marker_id, cases in events_by_marker.items():
                if len(cases) < 5:
                    continue
                signature = MarkerPatternSignatureService.build_signature(cases, "CORE")
                validation = MarkerPatternSignatureService.validate(cases, "CORE")
                if signature["status"] != "TESTABLE" or validation["distribution"] is None:
                    continue
                baselines[marker_id] = {"meta": marker_meta[marker_id], "cases": cases,
                                        "signature": signature, "validation": validation}
            self._put_cached_baselines(cache_key, baselines)
        else:
            prices = self._bulk_recent_prices([row["stock_id"] for row in universe], analysis_date)
        signature_ms = int((time.perf_counter() - signature_started) * 1000)

        feature_started = time.perf_counter()
        current_features: dict[int, dict[str, float]] = {}
        for stock in universe:
            rows = prices.get(stock["stock_id"], [])
            if rows and str(rows[0]["trade_date"])[:10] == analysis_date:
                status, features, _missing = PatternFeatureService.core(rows)
                if status == "READY" and features is not None:
                    current_features[stock["stock_id"]] = features
        feature_ms = int((time.perf_counter() - feature_started) * 1000)

        similarity_started = time.perf_counter()
        candidate_stocks: list[dict[str, Any]] = []
        details: dict[tuple[int, int], dict[str, Any]] = {}
        marker_counts = {marker_id: 0 for marker_id in baselines}
        marker_similarity_rows: dict[int, list[dict[str, Any]]] = {marker_id: [] for marker_id in baselines}
        for stock in universe:
            features = current_features.get(stock["stock_id"])
            if features is None:
                continue
            signals = []
            for marker_id, baseline in baselines.items():
                scored = MarkerPatternSignatureService.score(features, baseline["signature"])
                distribution = baseline["validation"]["distribution"]
                if scored is None:
                    continue
                similarity = float(scored["pattern_similarity"])
                loo_values = [float(row["pattern_similarity"]) for row in baseline["validation"]["cases"]]
                marker_similarity_rows[marker_id].append({
                    **stock, "similarity": similarity,
                    "empirical_percentile": sum(value <= similarity for value in loo_values) / len(loo_values) * 100,
                })
                band = self._band(similarity, distribution)
                if band is None:
                    continue
                percentile = sum(value <= similarity for value in loo_values) / len(loo_values) * 100
                meta = baseline["meta"]
                signal = {
                    **meta, "current_pattern_similarity": similarity, "candidate_band": band,
                    "empirical_percentile": percentile, "loo_p25": float(distribution["p25"]),
                    "loo_median": float(distribution["median"]), "loo_p75": float(distribution["p75"]),
                    "training_case_count": len(baseline["cases"]),
                }
                signals.append(signal)
                marker_counts[marker_id] += 1
                details[(stock["stock_id"], marker_id)] = {
                    "analysis_date": analysis_date, **stock, "signal": signal,
                    "top_feature_differences": [{
                        "key": row["key"], "label": row["label"], "unit": row["unit"],
                        "current_value": row["case_value"], "signature_median": row["signature_median"],
                        "robust_distance": row["robust_distance"],
                    } for row in scored["feature_distances"][:5]], "storage_policy": "RUNTIME_ONLY",
                }
            if signals:
                signals.sort(key=lambda row: (BAND_RANK[row["candidate_band"]], -row["empirical_percentile"], -row["current_pattern_similarity"], row["marker_name"]))
                candidate_stocks.append({**stock, "signals": signals})
        candidate_stocks.sort(key=lambda row: (BAND_RANK[row["signals"][0]["candidate_band"]],
                                                -row["signals"][0]["empirical_percentile"], row["stock_name"]))
        similarity_ms = int((time.perf_counter() - similarity_started) * 1000)
        marker_summaries = []
        for marker_id, baseline in baselines.items():
            distribution = baseline["validation"]["distribution"]
            marker_summaries.append({
                "marker_id": marker_id, "marker_name": baseline["meta"]["marker_name"],
                "training_case_count": len(baseline["cases"]), "loo_p25": distribution["p25"],
                "loo_median": distribution["median"], "loo_p75": distribution["p75"],
                "candidate_count": marker_counts[marker_id],
            })
        if not include_diagnostics:
            total_ms = int((time.perf_counter() - total_started) * 1000)
            return {
                "analysis_date": analysis_date, "universe_count": len(universe),
                "evaluable_stock_count": len(current_features),
                "incomplete_stock_count": len(universe) - len(current_features),
                "eligible_marker_count": len(baselines),
                "candidate_pair_count": sum(len(row["signals"]) for row in candidate_stocks),
                "candidate_stock_count": len(candidate_stocks),
                "algorithm": {"feature_schema_version": FEATURE_SCHEMA_VERSION,
                              "pattern_signature_version": MARKER_PATTERN_SIGNATURE_VERSION,
                              "similarity_algorithm_version": PATTERN_SIMILARITY_ALGORITHM_VERSION,
                              "candidate_policy_version": CANDIDATE_POLICY_VERSION},
                "marker_summaries": marker_summaries, "stocks": candidate_stocks,
                "timings": {"universe_ms": universe_ms, "signature_ms": signature_ms,
                            "feature_ms": feature_ms, "similarity_ms": similarity_ms,
                            "total_ms": total_ms, "sql_query_count": self.query_count},
                "storage_policy": "RUNTIME_ONLY",
            }, details
        threshold_keys = ("p25", "median", "p75", "p90")
        policy_stock_hits: dict[str, dict[int, int]] = {key: defaultdict(int) for key in threshold_keys}
        diagnostic_markers = []
        shadow_stock_hits: dict[int, int] = defaultdict(int)
        p25_pair_count = sum(marker_counts.values())
        for marker_id, baseline in baselines.items():
            loo_distribution = baseline["validation"]["distribution"]
            current_rows = sorted(marker_similarity_rows[marker_id], key=lambda row: (-row["similarity"], row["stock_name"]))
            current_distribution = self._distribution([row["similarity"] for row in current_rows])
            if current_distribution is None:
                continue
            thresholds = {}
            for key in threshold_keys:
                threshold = float(loo_distribution[key])
                passing = [row for row in current_rows if row["similarity"] >= threshold]
                for row in passing:
                    policy_stock_hits[key][row["stock_id"]] += 1
                thresholds[key] = {
                    "value": threshold, "candidate_count": len(passing),
                    "candidate_ratio": len(passing) / len(current_rows) * 100 if current_rows else 0.0,
                    "samples": [{
                        "stock_id": row["stock_id"], "stock_code": row["stock_code"],
                        "stock_name": row["stock_name"], "theme_names": row["theme_names"],
                        "similarity": row["similarity"], "empirical_percentile": row["empirical_percentile"],
                        "is_current_candidate": row["similarity"] >= float(loo_distribution["p25"]),
                    } for row in passing[:10]],
                }
            bounds = {
                "p90_or_above": lambda value: value >= float(loo_distribution["p90"]),
                "p75_to_p90": lambda value: float(loo_distribution["p75"]) <= value < float(loo_distribution["p90"]),
                "median_to_p75": lambda value: float(loo_distribution["median"]) <= value < float(loo_distribution["p75"]),
                "p25_to_median": lambda value: float(loo_distribution["p25"]) <= value < float(loo_distribution["median"]),
                "below_p25": lambda value: value < float(loo_distribution["p25"]),
            }
            segments = {}
            for key, predicate in bounds.items():
                rows = [row for row in current_rows if predicate(row["similarity"])]
                segments[key] = {"count": len(rows), "samples": [{
                    "stock_id": row["stock_id"], "stock_code": row["stock_code"],
                    "stock_name": row["stock_name"], "theme_names": row["theme_names"],
                    "similarity": row["similarity"], "empirical_percentile": row["empirical_percentile"],
                    "is_current_candidate": row["similarity"] >= float(loo_distribution["p25"]),
                } for row in rows[:3]]}
            meta = baseline["meta"]
            friendly, shadow_stock_ids = MarkerCandidatePolicyResearchService.evaluate(
                loo_distribution=loo_distribution,
                current_distribution=current_distribution,
                current_rows=current_rows,
                thresholds=thresholds,
            )
            for stock_id in shadow_stock_ids:
                shadow_stock_hits[stock_id] += 1
            diagnostic_markers.append({
                **meta, "training_s_count": len(baseline["cases"]),
                "loo_evaluated_count": int(baseline["validation"]["evaluated_count"]),
                "loo_distribution": {key: float(loo_distribution[key]) for key in ("min", "p10", "p25", "median", "p75", "p90", "max")},
                "current_evaluable_count": len(current_rows), "current_distribution": current_distribution,
                "median_gap": float(loo_distribution["median"]) - current_distribution["median"],
                "p75_gap": float(loo_distribution["p75"]) - current_distribution["p75"],
                "thresholds": thresholds, "segments": segments,
                "current_pair_contribution_ratio": marker_counts[marker_id] / p25_pair_count * 100 if p25_pair_count else 0.0,
                "p90_sample_warning": "학습 사례가 적으면 P90 기준은 표본 변화에 크게 영향을 받을 수 있습니다.",
                "friendly": friendly,
            })
        policies = {
            key: {
                "candidate_pair_count": sum(hits.values()),
                "candidate_stock_count": len(hits),
                "multiple_marker_stock_count": sum(count > 1 for count in hits.values()),
            } for key, hits in policy_stock_hits.items()
        }
        total_ms = int((time.perf_counter() - total_started) * 1000)
        response = {
            "analysis_date": analysis_date, "universe_count": len(universe),
            "evaluable_stock_count": len(current_features),
            "incomplete_stock_count": len(universe) - len(current_features),
            "eligible_marker_count": len(baselines),
            "candidate_pair_count": sum(len(row["signals"]) for row in candidate_stocks),
            "candidate_stock_count": len(candidate_stocks),
            "algorithm": {"feature_schema_version": FEATURE_SCHEMA_VERSION,
                          "pattern_signature_version": MARKER_PATTERN_SIGNATURE_VERSION,
                          "similarity_algorithm_version": PATTERN_SIMILARITY_ALGORITHM_VERSION,
                          "candidate_policy_version": CANDIDATE_POLICY_VERSION},
            "marker_summaries": marker_summaries, "stocks": candidate_stocks,
            "diagnostics": {"current_policy": "P25", "baseline_policy_version": BASELINE_POLICY_VERSION,
                            "shadow_policy": {
                                "candidate_pair_count": sum(shadow_stock_hits.values()),
                                "candidate_stock_count": len(shadow_stock_hits),
                                "multiple_marker_stock_count": sum(count > 1 for count in shadow_stock_hits.values()),
                            },
                            "shadow_policy_status": "VALIDATING", "shadow_policy_version": SHADOW_POLICY_VERSION,
                            "markers": diagnostic_markers, "policies": policies, "storage_policy": "RUNTIME_ONLY"},
            "timings": {"universe_ms": universe_ms, "signature_ms": signature_ms,
                        "feature_ms": feature_ms, "similarity_ms": similarity_ms,
                        "total_ms": total_ms, "sql_query_count": self.query_count},
            "storage_policy": "RUNTIME_ONLY",
        }
        return response, details

    def scan(self, requested_date: date | None = None) -> dict[str, Any]:
        response, _details = self._run(requested_date)
        return response

    def scan_summary(self, requested_date: date | None = None) -> dict[str, Any]:
        response, _details = self._run(requested_date, include_diagnostics=False)
        response.pop("diagnostics", None)
        return response

    def diagnostics(self, requested_date: date | None = None) -> dict[str, Any]:
        response, _details = self._run(requested_date, include_diagnostics=True)
        return response["diagnostics"]

    def detail(self, stock_id: int, marker_id: int, analysis_date: date | None = None) -> dict[str, Any]:
        """Build one stock/marker detail without rerunning the current-universe scan."""
        total_started = time.perf_counter()
        if analysis_date is None:
            universe = self._universe()
            resolved = self._analysis_date([row["stock_id"] for row in universe], None)
            if resolved is None:
                raise HTTPException(404, "현재 기준일을 찾을 수 없습니다.")
            analysis_date_text = resolved
        else:
            analysis_date_text = analysis_date.isoformat()

        metadata_started = time.perf_counter()
        stock_rows = self._execute("""
            SELECT stock.id stock_id, stock.stock_code, stock.stock_name, theme.theme_name
            FROM market_theme_stocks mapping
            JOIN market_themes theme ON theme.id=mapping.theme_id
            JOIN stocks stock ON stock.id=mapping.stock_id
            WHERE stock.id=:stock_id AND COALESCE(mapping.is_active,1)=1
              AND theme.is_active=1 AND COALESCE(theme.theme_level,'THEME')='THEME'
              AND COALESCE(stock.is_active,1)=1
            ORDER BY theme.sort_order, theme.theme_name
        """, {"stock_id": stock_id}).mappings().all()
        if not stock_rows:
            raise HTTPException(404, "현재 연결종목을 찾을 수 없습니다.")
        stock = {
            "stock_id": int(stock_rows[0]["stock_id"]),
            "stock_code": str(stock_rows[0]["stock_code"]),
            "stock_name": str(stock_rows[0]["stock_name"]),
            "theme_names": list(dict.fromkeys(str(row["theme_name"]) for row in stock_rows)),
        }
        metadata_ms = int((time.perf_counter() - metadata_started) * 1000)

        signature_started = time.perf_counter()
        events = [dict(row) for row in self._execute("""
            SELECT marker.id marker_id, marker.name marker_name, marker.symbol marker_symbol,
                   marker.marker_group_id, marker_group.name marker_group,
                   marker_group.color marker_group_color,
                   event.id chart_marker_event_id, event.stock_id, event.marker_date d0
            FROM chart_markers marker
            JOIN chart_marker_groups marker_group ON marker_group.id=marker.marker_group_id
            JOIN chart_marker_events event ON event.marker_id=marker.id
            LEFT JOIN chart_marker_learning_decisions decision ON decision.chart_marker_event_id=event.id
            WHERE marker.id=:marker_id AND marker.is_active=1 AND marker_group.is_active=1
              AND event.review_result IN ('S','SUCCESS')
              AND event.marker_date<=:analysis_date
              AND COALESCE(decision.decision,'INCLUDE')<>'EXCLUDE'
            ORDER BY event.marker_date, event.id
        """, {"marker_id": marker_id, "analysis_date": analysis_date_text}).mappings().all()]
        if not events:
            raise HTTPException(404, "학습 가능한 Marker 성공 사례를 찾을 수 없습니다.")
        price_stock_ids = sorted({stock_id} | {int(event["stock_id"]) for event in events})
        prices = self._bulk_prices(price_stock_ids, analysis_date_text)
        cases = []
        for event in events:
            features = self._core_at(prices.get(int(event["stock_id"]), []), str(event["d0"])[:10])
            if features is not None:
                cases.append({
                    "chart_marker_event_id": int(event["chart_marker_event_id"]),
                    "stock_id": int(event["stock_id"]), "stock_code": "", "stock_name": "",
                    "d0": str(event["d0"])[:10], "review_result": "S", "learning_decision": None,
                    "core_status": "READY", "core_features": features,
                })
        if len(cases) < 5:
            raise HTTPException(404, "현재 기준일의 학습 가능 Marker를 찾을 수 없습니다.")
        signature = MarkerPatternSignatureService.build_signature(cases, "CORE")
        validation = MarkerPatternSignatureService.validate(cases, "CORE")
        distribution = validation.get("distribution")
        if signature["status"] != "TESTABLE" or distribution is None:
            raise HTTPException(404, "현재 기준일의 학습 가능 Marker를 찾을 수 없습니다.")
        signature_ms = int((time.perf_counter() - signature_started) * 1000)

        feature_started = time.perf_counter()
        current_rows = prices.get(stock_id, [])
        if not current_rows or str(current_rows[0]["trade_date"])[:10] != analysis_date_text:
            raise HTTPException(404, "현재 기준일의 종목 Feature를 찾을 수 없습니다.")
        status, current_features, _missing = PatternFeatureService.core(current_rows)
        if status != "READY" or current_features is None:
            raise HTTPException(404, "현재 기준일의 종목 Feature를 찾을 수 없습니다.")
        feature_ms = int((time.perf_counter() - feature_started) * 1000)

        similarity_started = time.perf_counter()
        scored = MarkerPatternSignatureService.score(current_features, signature)
        if scored is None:
            raise HTTPException(404, "현재 기준일의 Pattern 후보를 찾을 수 없습니다.")
        similarity = float(scored["pattern_similarity"])
        band = self._band(similarity, distribution)
        loo_values = [float(row["pattern_similarity"]) for row in validation["cases"]]
        meta = events[0]
        signal = {
            **{key: meta[key] for key in (
                "marker_id", "marker_name", "marker_symbol", "marker_group_id", "marker_group", "marker_group_color"
            )},
            "current_pattern_similarity": similarity,
            "candidate_band": band or "BELOW_CANDIDATE",
            "empirical_percentile": sum(value <= similarity for value in loo_values) / len(loo_values) * 100,
            "loo_p25": float(distribution["p25"]), "loo_median": float(distribution["median"]),
            "loo_p75": float(distribution["p75"]), "training_case_count": len(cases),
        }
        differences = [{
            "key": row["key"], "label": row["label"], "unit": row["unit"],
            "current_value": row["case_value"], "signature_median": row["signature_median"],
            "robust_distance": row["robust_distance"],
        } for row in scored["feature_distances"][:5]]
        similarity_ms = int((time.perf_counter() - similarity_started) * 1000)
        total_ms = int((time.perf_counter() - total_started) * 1000)
        logger.debug(
            "current-pattern detail stock=%s marker=%s metadata_ms=%s signature_ms=%s feature_ms=%s "
            "similarity_ms=%s total_ms=%s sql_queries=%s",
            stock_id, marker_id, metadata_ms, signature_ms, feature_ms, similarity_ms, total_ms, self.query_count,
        )
        return {
            "analysis_date": analysis_date_text, **stock, "signal": signal,
            "top_feature_differences": differences, "storage_policy": "RUNTIME_ONLY",
        }
