from __future__ import annotations

import math
from datetime import date, datetime, time
from statistics import mean, median
from threading import Condition, RLock
from time import monotonic
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.schemas.drct_insight_schema import DrctInsightTodayResponse
from backend.app.services.market_theme_observation_service import MarketThemeObservationService
from backend.app.services.marker_current_pattern_scan_service import MarkerCurrentPatternScanService
from backend.app.services.realtime_theme_service import RealtimeThemeService
from backend.app.services.us_kr_theme_link_service import UsKrThemeLinkService


PATTERN_REQUIRED_SAMPLE_COUNT = 5
FOCUS_CANDIDATE_LIMIT = 8
FOCUS_MAX_PER_THEME = 2
INSIGHT_RULE_VERSION = "P3B_V1"


def _percentile(values: list[float], percent: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percent / 100
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    weight = position - lower
    return float(ordered[lower] * (1 - weight) + ordered[upper] * weight)


def _percentile_rank(values: list[float], value: float | None) -> float | None:
    if value is None or not values:
        return None
    return round(sum(item <= value for item in values) / len(values) * 100, 2)


class DrctInsightService:
    """Runtime-only convergence view over existing DrCT sources."""

    _today_cache_ttl_seconds = 15.0
    _today_cache: dict[object, tuple[float, DrctInsightTodayResponse]] = {}
    _today_inflight: set[object] = set()
    _today_condition = Condition(RLock())

    def __init__(self, db: Session) -> None:
        self.db = db

    @classmethod
    def invalidate_today_cache(cls, bind: object | None = None) -> None:
        """Drop transient Today data without persisting source or response detail."""
        with cls._today_condition:
            if bind is None:
                cls._today_cache.clear()
            else:
                cls._today_cache.pop(bind, None)

    def _publish_today_cache(self, result: DrctInsightTodayResponse) -> None:
        bind = self.db.get_bind()
        with self._today_condition:
            self._today_cache[bind] = (monotonic() + self._today_cache_ttl_seconds, result)
            while len(self._today_cache) > 8:
                self._today_cache.pop(next(iter(self._today_cache)))
            self._today_condition.notify_all()

    def today(self, force_refresh: bool = False) -> DrctInsightTodayResponse:
        """Return a short-lived runtime snapshot and coalesce concurrent rebuilds."""
        bind = self.db.get_bind()
        with self._today_condition:
            cached = self._today_cache.get(bind)
            if not force_refresh and cached and cached[0] > monotonic():
                return cached[1]
            while bind in self._today_inflight:
                self._today_condition.wait()
                cached = self._today_cache.get(bind)
                if cached:
                    return cached[1]
            self._today_inflight.add(bind)
        try:
            result = self._build_today()
        except Exception:
            with self._today_condition:
                self._today_inflight.discard(bind)
                self._today_condition.notify_all()
            raise
        with self._today_condition:
            self._today_cache[bind] = (monotonic() + self._today_cache_ttl_seconds, result)
            while len(self._today_cache) > 8:
                self._today_cache.pop(next(iter(self._today_cache)))
            self._today_inflight.discard(bind)
            self._today_condition.notify_all()
        return result

    @staticmethod
    def _theme_gate(rank: int | None, pass_count: int) -> str:
        if rank is None:
            return "NO_DATA"
        return "PASS" if rank <= pass_count else "WATCH"

    @staticmethod
    def _flow_gate(score: float | None, p25: float | None, median: float | None) -> str:
        if score is None or p25 is None or median is None:
            return "NO_DATA"
        if score >= median:
            return "PASS"
        if score >= p25:
            return "WATCH"
        return "WEAK"

    @staticmethod
    def _pattern_gate(edge: float | None, band: str, p25: float | None, median: float | None) -> str:
        if edge is None or p25 is None or median is None:
            return "NOT_READY"
        if band in {"VERY_SIMILAR", "HIGH_SIMILARITY"} and edge > 0 and edge >= median:
            return "PASS"
        if edge > 0 and edge >= p25:
            return "WATCH"
        return "WEAK"

    @staticmethod
    def _is_final_candidate(theme_gate: str, flow_gate: str, pattern_gate: str) -> bool:
        return theme_gate == "PASS" and flow_gate in {"PASS", "WATCH"} and pattern_gate == "PASS"

    @staticmethod
    def _pattern_status(pattern_gate: str, band: str, failure_count: int) -> str:
        if failure_count >= PATTERN_REQUIRED_SAMPLE_COUNT:
            return {"PASS": "VERIFIED", "WATCH": "WATCH", "WEAK": "WEAK"}.get(pattern_gate, "NOT_READY")
        if band in {"VERY_SIMILAR", "HIGH_SIMILARITY"}:
            return "PROMISING"
        return "NOT_READY"

    @staticmethod
    def _is_preliminary_candidate(theme_gate: str, flow_gate: str, pattern_status: str) -> bool:
        return theme_gate == "PASS" and flow_gate in {"PASS", "WATCH"} and pattern_status == "PROMISING"

    @staticmethod
    def _us_strength(value: float | None) -> str | None:
        if value is None:
            return None
        absolute = abs(value)
        return "STRONG" if absolute >= 2 else "MODERATE" if absolute >= 1 else "WEAK"

    @classmethod
    def _us_lead(cls, item: Any | None, metric: str = "theme_strength") -> dict[str, Any]:
        if item is None:
            return {"linked": False, "relation_status": "MISSING"}
        value = float(item.latest_value) if item.latest_value is not None else None
        direction = "UP" if value is not None and value > 0 else "DOWN" if value is not None and value < 0 else "FLAT" if value is not None else None
        return {
            "linked": True, "link_id": item.link_id, "us_theme_id": item.us_theme_id,
            "us_theme_name": item.us_theme_name, "metric": metric, "value": value,
            "direction": direction, "strength": cls._us_strength(value),
            "breadth_ratio": item.breadth_ratio,
            "relation_status": "AVAILABLE" if item.available else "MISSING",
            "response_rate": item.response_rate, "sample_count": item.sample_count,
            "source_date": item.latest_us_date, "kr_response_date": item.kr_target_date,
        }

    @staticmethod
    def _source_status(source_date: str | None, reference_date: str | None, *, available: bool) -> str:
        if not available:
            return "NOT_READY"
        if source_date and reference_date:
            try:
                if abs((date.fromisoformat(reference_date[:10]) - date.fromisoformat(source_date[:10])).days) > 7:
                    return "STALE"
            except ValueError:
                pass
        return "READY"

    @staticmethod
    def _execution(status: str | None) -> str:
        return {
            "매수후보": "READY", "보유중": "TRIGGERED", "제외": "INVALID",
            "READY": "READY", "TRIGGERED": "TRIGGERED", "INVALID": "INVALID",
        }.get(str(status or "").upper() if status and status.isascii() else str(status or ""), "WAIT")

    def _watch_rows(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.db.execute(text("""
            SELECT watch.id watchlist_id, watch.stock_id, watch.status watch_status
            FROM watchlist watch
            WHERE watch.is_active=1
            ORDER BY watch.updated_at DESC, watch.id DESC
        """)).mappings().all()]

    def _stock_change_rates(self, analysis_date: str | None) -> dict[int, float]:
        if not analysis_date:
            return {}
        rows = self.db.execute(text("""
            SELECT stock_id, change_rate
            FROM stock_daily_prices
            WHERE trade_date=:analysis_date AND change_rate IS NOT NULL
        """), {"analysis_date": analysis_date}).mappings().all()
        return {int(row["stock_id"]): float(row["change_rate"]) for row in rows}

    def _realtime_stock_change_rates(self, trade_date: str | None) -> dict[int, float]:
        if not trade_date:
            return {}
        rows = self.db.execute(text("""
            SELECT stock_id, MAX(change_rate) change_rate
            FROM market_theme_realtime_returns
            WHERE trade_date=:trade_date AND change_rate IS NOT NULL
            GROUP BY stock_id
        """), {"trade_date": trade_date}).mappings().all()
        return {int(row["stock_id"]): float(row["change_rate"]) for row in rows}

    @staticmethod
    def _select_focus_candidate_ids(rows: list[dict[str, Any]]) -> list[int]:
        """Select an explainable, diversified Focus set without a composite score."""
        preliminary = [row for row in rows if row.get("preliminary_candidate")]
        preliminary.sort(key=lambda row: (
            row["gates"].get("flow") != "PASS",
            not (
                row.get("us_lead", {}).get("relation_status") == "AVAILABLE"
                and row.get("us_lead", {}).get("direction") == "UP"
            ),
            row.get("observation_rank") or 99999,
            -float(row.get("success_similarity") or 0),
            row.get("pattern_status") != "PROMISING",
            row.get("relative_strength") is None,
            -float(row.get("relative_strength") or 0),
            row.get("change_rate") is None,
            -float(row.get("change_rate") or 0),
            row.get("stock_name") or "",
        ))
        selected: list[int] = []
        per_theme: dict[int, int] = {}
        for row in preliminary:
            theme_id = int(row["theme_id"])
            if per_theme.get(theme_id, 0) >= FOCUS_MAX_PER_THEME:
                continue
            selected.append(int(row["stock_id"]))
            per_theme[theme_id] = per_theme.get(theme_id, 0) + 1
            if len(selected) >= FOCUS_CANDIDATE_LIMIT:
                break
        return selected

    @staticmethod
    def _market_mode(now: datetime | None = None) -> str:
        current = now or datetime.fromisoformat(now_kst())
        if current.weekday() >= 5:
            return "POST_MARKET"
        if current.time() < time(9, 0):
            return "PRE_MARKET"
        if current.time() < time(15, 30):
            return "INTRADAY"
        return "POST_MARKET"

    def _stored_focus_ids(self, analysis_date: str | None) -> list[int]:
        if not analysis_date:
            return []
        rows = self.db.execute(text("""
            SELECT stock_id FROM drct_insight_candidate_evaluations
            WHERE analysis_date=:analysis_date AND candidate_level='FOCUS'
            ORDER BY id
        """), {"analysis_date": analysis_date}).mappings().all()
        return [int(row["stock_id"]) for row in rows]

    @staticmethod
    def _bind_ids(prefix: str, values: list[int]) -> tuple[str, dict[str, int]]:
        params = {f"{prefix}_{index}": value for index, value in enumerate(values)}
        return ",".join(f":{key}" for key in params), params

    def _batch_outcomes(self, analysis_date: str | None, rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
        if not analysis_date or not rows:
            return {}
        stock_ids = sorted({int(row["stock_id"]) for row in rows})
        theme_ids = sorted({int(row["theme_id"]) for row in rows if row.get("theme_id") is not None})
        stock_clause, stock_params = self._bind_ids("stock", stock_ids)
        price_rows = self.db.execute(text(f"""
            SELECT stock_id, close_price, change_rate
            FROM stock_daily_prices
            WHERE trade_date=:analysis_date AND stock_id IN ({stock_clause})
        """), {"analysis_date": analysis_date, **stock_params}).mappings().all()
        price_by_stock = {int(row["stock_id"]): row for row in price_rows}
        theme_by_id: dict[int, float] = {}
        if theme_ids:
            theme_clause, theme_params = self._bind_ids("theme", theme_ids)
            theme_rows = self.db.execute(text(f"""
                SELECT theme_id, avg_change_rate
                FROM market_theme_daily_returns
                WHERE return_date=:analysis_date AND theme_id IN ({theme_clause})
            """), {"analysis_date": analysis_date, **theme_params}).mappings().all()
            theme_by_id = {int(row["theme_id"]): float(row["avg_change_rate"]) for row in theme_rows if row["avg_change_rate"] is not None}
        marker_rows = self.db.execute(text(f"""
            SELECT id, stock_id, review_result
            FROM chart_marker_events
            WHERE marker_date=:analysis_date AND stock_id IN ({stock_clause})
            ORDER BY reviewed_at DESC, id DESC
        """), {"analysis_date": analysis_date, **stock_params}).mappings().all()
        marker_by_stock: dict[int, Any] = {}
        for marker in marker_rows:
            marker_by_stock.setdefault(int(marker["stock_id"]), marker)
        outcomes: dict[int, dict[str, Any]] = {}
        for row in rows:
            stock_id = int(row["stock_id"])
            price = price_by_stock.get(stock_id)
            theme_return = theme_by_id.get(int(row["theme_id"])) if row.get("theme_id") is not None else None
            marker = marker_by_stock.get(stock_id)
            d0_return = float(price["change_rate"]) if price and price["change_rate"] is not None else None
            relative_return = round(d0_return - theme_return, 4) if d0_return is not None and theme_return is not None else None
            status = "NOT_READY" if d0_return is None else "READY" if theme_return is not None else "PARTIAL"
            marker_result = str(marker["review_result"]) if marker and marker["review_result"] in {"S", "F"} else "UNDECIDED" if marker else "UNRECORDED"
            outcomes[stock_id] = {
                "status": status, "analysis_date": analysis_date,
                "close_price": float(price["close_price"]) if price and price["close_price"] is not None else None,
                "d0_return": d0_return, "theme_d0_return": theme_return, "relative_return": relative_return,
                "direction": "UP" if d0_return is not None and d0_return > 0 else "DOWN" if d0_return is not None and d0_return < 0 else "FLAT" if d0_return is not None else "NOT_READY",
                "marker_status": marker_result, "marker_event_id": int(marker["id"]) if marker else None,
            }
        return outcomes

    @staticmethod
    def _review_queue(rows: list[dict[str, Any]], watch_ids: set[int]) -> list[dict[str, Any]]:
        reviews: list[dict[str, Any]] = []
        for row in rows:
            if not row.get("focus_candidate") and int(row["stock_id"]) not in watch_ids:
                continue
            outcome = row.get("outcome") or {}
            d0 = outcome.get("d0_return")
            relative = outcome.get("relative_return")
            execution = row["gates"].get("execution") or "WAIT"
            categories: list[str] = []
            reasons: list[str] = []
            if d0 is None:
                categories.append("OUTCOME_MISSING"); reasons.append("가격 데이터 최신수집 필요")
            else:
                if d0 >= 3 and relative is not None and relative >= 1:
                    categories.append("STRONG"); reasons.append(f"D0 {d0:+.1f}% · 테마 대비 {relative:+.1f}%p")
                if d0 < 0 or (relative is not None and relative <= -1.5):
                    categories.append("WEAK"); reasons.append(f"Focus/관찰 이후 상대성과 {relative:+.1f}%p" if relative is not None else f"D0 {d0:+.1f}%")
                if row.get("pattern_status") == "PROMISING" and (abs(d0) >= 3 or (relative is not None and abs(relative) >= 2)):
                    categories.append("PATTERN"); reasons.append("PROMISING 이후 결과가 명확해 Pattern 확인 가치가 높음")
            high = (
                (d0 is not None and d0 <= -3)
                or (execution in {"READY", "TRIGGERED"} and d0 is not None and d0 < 0)
                or "PATTERN" in categories or "STRONG" in categories
            )
            reviews.append({
                "stock_id": row["stock_id"], "stock_code": row["stock_code"], "stock_name": row["stock_name"],
                "theme_id": row.get("theme_id"), "theme_name": row.get("theme_name"),
                "focus_candidate": bool(row.get("focus_candidate")), "candidate_level": row["candidate_level"],
                "pattern_status": row["pattern_status"], "success_similarity": row["success_similarity"],
                "user_status": execution, "priority": "HIGH" if high else "NORMAL",
                "categories": categories, "reasons": reasons or ["일반 Focus/MY WATCH 결과 확인"], "outcome": outcome,
            })
        reviews.sort(key=lambda item: (item["priority"] != "HIGH", item["outcome"].get("d0_return") is None, -(abs(item["outcome"].get("relative_return") or 0)), item["stock_name"]))
        return reviews

    def _pattern_review_counts(self, analysis_date: str | None) -> tuple[int, int]:
        if not analysis_date:
            return 0, 0
        rows = self.db.execute(text("""
            SELECT CASE WHEN UPPER(event.review_result) IN ('F','FAILURE') THEN 'F' ELSE 'S' END label,
                   COUNT(*) case_count
            FROM chart_marker_events event
            JOIN chart_markers marker ON marker.id=event.marker_id AND marker.is_active=1
            JOIN chart_marker_groups marker_group ON marker_group.id=marker.marker_group_id AND marker_group.is_active=1
            LEFT JOIN chart_marker_learning_decisions decision ON decision.chart_marker_event_id=event.id
            WHERE UPPER(event.review_result) IN ('S','SUCCESS','F','FAILURE')
              AND event.marker_date<=:analysis_date
              AND COALESCE(decision.decision,'INCLUDE')<>'EXCLUDE'
            GROUP BY CASE WHEN UPPER(event.review_result) IN ('F','FAILURE') THEN 'F' ELSE 'S' END
        """), {"analysis_date": analysis_date}).mappings().all()
        counts = {str(row["label"]): int(row["case_count"]) for row in rows}
        return counts.get("S", 0), counts.get("F", 0)

    def _build_today(self) -> DrctInsightTodayResponse:
        observation = MarketThemeObservationService(self.db).latest()
        realtime = RealtimeThemeService(self.db).get_treemap()
        pattern = MarkerCurrentPatternScanService(self.db).scan_summary()
        us_error = False
        try:
            us_observation = UsKrThemeLinkService(self.db).today_observation(window=120, us_metric="theme_strength")
        except Exception:
            us_observation = None
            us_error = True

        observation_items = list(observation.items)
        observation_count = len([item for item in observation_items if item.observation_rank is not None])
        theme_pass_count = max(5, math.ceil(observation_count * .20)) if observation_count else 0
        flow_values = [float(item.flow_score) for item in observation_items if item.flow_score is not None]
        theme_values = [float(item.relative_strength_score) for item in observation_items if item.relative_strength_score is not None]
        flow_p25 = _percentile(flow_values, 25)
        flow_median = _percentile(flow_values, 50)
        realtime_by_id = {item.theme_id: item for item in realtime.themes}
        us_by_kr_theme = {item.kr_theme_id: item for item in (us_observation.items if us_observation else [])}

        theme_rows: list[dict[str, Any]] = []
        theme_by_name: dict[str, dict[str, Any]] = {}
        for item in observation_items:
            theme_gate = self._theme_gate(item.observation_rank, theme_pass_count)
            flow_gate = self._flow_gate(item.flow_score, flow_p25, flow_median)
            live = realtime_by_id.get(item.theme_id)
            us_item = us_by_kr_theme.get(item.theme_id)
            us_lead = self._us_lead(us_item)
            us_catalyst = us_lead.get("strength") or "NONE"
            why: list[str] = []
            warnings: list[str] = []
            if item.observation_rank is not None:
                why.append(f"관찰순위 #{item.observation_rank}")
            if us_lead.get("relation_status") == "AVAILABLE":
                why.insert(0, f"미국 {us_lead['us_theme_name']} {us_lead['value']:+.1f}%")
            if flow_gate == "PASS":
                why.append("수급 강도 상위 구간")
            if live and live.avg_change_rate is not None:
                why.append(f"장중 {live.avg_change_rate:+.1f}%")
            if live and live.valid_stock_count:
                why.append(f"확산 {live.valid_stock_count}/{live.linked_stock_count}")
            if not live:
                warnings.append("실시간 Snapshot 없음")
            row = {
                "theme_id": item.theme_id, "theme_name": item.theme_name,
                "observation_rank": item.observation_rank,
                "change_rate": live.avg_change_rate if live else item.base_change_rate,
                "theme_strength": live.theme_strength if live else None,
                "valid_stock_count": live.valid_stock_count if live else 0,
                "linked_stock_count": live.linked_stock_count if live else 0,
                "flow_score": item.flow_score,
                "theme_score": item.relative_strength_score,
                "theme_percentile": _percentile_rank(theme_values, item.relative_strength_score),
                "flow_percentile": _percentile_rank(flow_values, item.flow_score),
                "us_catalyst": us_catalyst, "us_lead": us_lead,
                "breadth": f"{live.valid_stock_count}/{live.linked_stock_count}" if live else None,
                "linked_candidate_count": 0, "preliminary_candidate_count": 0,
                "focus_candidate_count": 0, "final_candidate_count": 0,
                "gates": {"theme": theme_gate, "flow": flow_gate},
                "why_items": why, "warning_items": warnings,
            }
            theme_rows.append(row)
            theme_by_name[item.theme_name] = row

        edge_values = [
            float(signal["pattern_edge"])
            for stock in pattern.get("stocks", []) for signal in stock.get("signals", [])
            if signal.get("pattern_edge") is not None
        ]
        edge_p25 = _percentile(edge_values, 25)
        edge_median = _percentile(edge_values, 50)
        daily_stock_change = self._stock_change_rates(pattern.get("analysis_date"))
        realtime_stock_change = self._realtime_stock_change_rates(realtime.trade_date)
        watch_rows = self._watch_rows()
        watch_by_stock = {int(row["stock_id"]): row for row in watch_rows}

        stock_rows: list[dict[str, Any]] = []
        for stock in pattern.get("stocks", []):
            signals = list(stock.get("signals") or [])
            if not signals:
                continue
            signals.sort(key=lambda signal: (
                signal.get("pattern_edge") is None,
                -(signal.get("pattern_edge") or -999),
                -signal.get("success_similarity", signal.get("current_pattern_similarity", 0)),
            ))
            signal = signals[0]
            theme = min(
                (theme_by_name[name] for name in stock.get("theme_names", []) if name in theme_by_name),
                key=lambda row: row.get("observation_rank") or 99999,
                default=None,
            )
            edge = signal.get("pattern_edge")
            pattern_gate = self._pattern_gate(edge, signal["candidate_band"], edge_p25, edge_median)
            failure_count = int(signal.get("failure_training_case_count") or 0)
            pattern_status = self._pattern_status(pattern_gate, signal["candidate_band"], failure_count)
            theme_gate = theme["gates"]["theme"] if theme else "NO_DATA"
            flow_gate = theme["gates"]["flow"] if theme else "NO_DATA"
            watch = watch_by_stock.get(int(stock["stock_id"]))
            execution = self._execution(watch.get("watch_status") if watch else None)
            final = self._is_final_candidate(theme_gate, flow_gate, pattern_gate)
            preliminary = not final and self._is_preliminary_candidate(theme_gate, flow_gate, pattern_status)
            candidate_level = "FINAL" if final else "PRELIMINARY" if preliminary else "NONE"
            convergence = sum((theme_gate == "PASS", flow_gate in {"PASS", "WATCH"}, pattern_status in {"VERIFIED", "PROMISING"}))
            success = float(signal.get("success_similarity", signal["current_pattern_similarity"]))
            failure = signal.get("failure_similarity")
            why = []
            if theme:
                why.append(f"{theme['theme_name']} 관찰순위 #{theme['observation_rank']}" if theme.get("observation_rank") else theme["theme_name"])
                if theme["us_lead"].get("relation_status") == "AVAILABLE":
                    why.insert(0, f"미국 {theme['us_lead']['us_theme_name']} {theme['us_lead']['value']:+.1f}%")
            why.append(f"성공 패턴 {success:.0f}")
            if failure is not None:
                why.append(f"실패 패턴 {float(failure):.0f}")
                why.append(f"Pattern Edge {float(edge):+.0f}")
            warnings = [] if failure is not None else ["실패 Marker 비교 표본 부족", "Pattern Edge 미확정"]
            if preliminary:
                why.append("Preliminary Candidate")
            stock_change_rate = realtime_stock_change.get(
                int(stock["stock_id"]), daily_stock_change.get(int(stock["stock_id"]))
            )
            theme_change_rate = theme.get("change_rate") if theme else None
            relative_strength = (
                round(float(stock_change_rate) - float(theme_change_rate), 4)
                if stock_change_rate is not None and theme_change_rate is not None else None
            )
            row = {
                "stock_id": int(stock["stock_id"]), "stock_code": stock["stock_code"],
                "stock_name": stock["stock_name"], "theme_id": theme["theme_id"] if theme else None,
                "theme_name": theme["theme_name"] if theme else (stock.get("theme_names") or [None])[0],
                "observation_rank": theme.get("observation_rank") if theme else None,
                "change_rate": stock_change_rate,
                "theme_change_rate": theme_change_rate,
                "theme_strength": theme.get("theme_strength") if theme else None,
                "theme_valid_stock_count": int(theme.get("valid_stock_count") or 0) if theme else 0,
                "theme_linked_stock_count": int(theme.get("linked_stock_count") or 0) if theme else 0,
                "relative_strength": relative_strength,
                "marker_id": int(signal["marker_id"]), "marker_name": signal["marker_name"],
                "candidate_band": signal["candidate_band"], "success_similarity": success,
                "failure_similarity": failure, "pattern_edge": edge,
                "success_sample_count": int(signal["training_case_count"]),
                "failure_sample_count": failure_count,
                "required_failure_sample_count": PATTERN_REQUIRED_SAMPLE_COUNT,
                "pattern_status": pattern_status, "candidate_level": candidate_level,
                "preliminary_candidate": preliminary, "final_candidate": final,
                "focus_candidate": False, "focus_rank": None,
                "us_lead": theme["us_lead"] if theme else self._us_lead(None),
                "convergence_level": convergence,
                "gates": {"theme": theme_gate, "flow": flow_gate, "pattern": pattern_gate, "execution": execution},
                "why_items": why, "warning_items": warnings,
            }
            stock_rows.append(row)
            if theme:
                theme["linked_candidate_count"] += 1
                theme["preliminary_candidate_count"] += int(preliminary)
                theme["final_candidate_count"] += int(final)

        analysis_date = pattern.get("analysis_date")
        stored_focus_ids = self._stored_focus_ids(analysis_date)
        evaluation_captured = bool(stored_focus_ids)
        focus_ids = stored_focus_ids or self._select_focus_candidate_ids(stock_rows)
        focus_rank_by_id = {stock_id: rank for rank, stock_id in enumerate(focus_ids, start=1)}
        theme_by_id = {int(row["theme_id"]): row for row in theme_rows}
        for row in stock_rows:
            focus_rank = focus_rank_by_id.get(int(row["stock_id"]))
            row["focus_candidate"] = focus_rank is not None
            row["focus_rank"] = focus_rank
            if focus_rank is not None and row.get("theme_id") in theme_by_id:
                theme_by_id[int(row["theme_id"])]["focus_candidate_count"] += 1

        stock_rows.sort(key=lambda row: (
            {"FINAL": 0, "PRELIMINARY": 1, "NONE": 2}[row["candidate_level"]],
            not row["focus_candidate"], row["focus_rank"] or 99999,
            -row["convergence_level"], -row["success_similarity"],
            row["pattern_edge"] is None, -(row["pattern_edge"] or -999), row["stock_name"],
        ))
        themes = [row for row in theme_rows if row["linked_candidate_count"] or row["gates"]["theme"] == "PASS"]
        themes.sort(key=lambda row: (row.get("observation_rank") or 99999, -row["final_candidate_count"]))

        stock_by_id = {row["stock_id"]: row for row in stock_rows}
        my_watch = []
        for watch in watch_rows:
            stock = stock_by_id.get(int(watch["stock_id"]))
            if stock:
                my_watch.append({**stock, **watch})

        watch_ids = {int(row["stock_id"]) for row in watch_rows}
        outcome_rows = [row for row in stock_rows if row.get("focus_candidate") or int(row["stock_id"]) in watch_ids]
        outcomes = self._batch_outcomes(analysis_date, outcome_rows)
        for row in stock_rows:
            row["outcome"] = outcomes.get(int(row["stock_id"]))
        for row in my_watch:
            row["outcome"] = outcomes.get(int(row["stock_id"]))
        review_queue = self._review_queue(stock_rows, watch_ids)

        focus_rows = [row for row in stock_rows if row.get("focus_candidate")]
        available_focus = [row for row in focus_rows if row.get("outcome", {}).get("d0_return") is not None]
        focus_returns = [float(row["outcome"]["d0_return"]) for row in available_focus]
        outcome_summary = {
            "focus_count": len(focus_rows), "available_count": len(available_focus),
            "positive_count": sum(value > 0 for value in focus_returns),
            "negative_count": sum(value < 0 for value in focus_returns),
            "average_d0_return": round(mean(focus_returns), 4) if focus_returns else None,
            "median_d0_return": round(median(focus_returns), 4) if focus_returns else None,
            "theme_outperform_count": sum((row["outcome"].get("relative_return") or 0) > 0 for row in available_focus if row["outcome"].get("relative_return") is not None),
            "review_count": len(review_queue),
            "high_review_count": sum(row["priority"] == "HIGH" for row in review_queue),
            "marker_recorded_count": sum(row["outcome"].get("marker_status") != "UNRECORDED" for row in review_queue),
            "not_ready_count": sum(row["outcome"].get("status") == "NOT_READY" for row in review_queue),
        }

        final_count = sum(bool(row["final_candidate"]) for row in stock_rows)
        preliminary_count = sum(bool(row["preliminary_candidate"]) for row in stock_rows)
        focus_count = sum(bool(row["focus_candidate"]) for row in stock_rows)
        ready_count = sum(row["gates"]["execution"] == "READY" for row in my_watch)
        last_updated = realtime.snapshot_at or (observation.run.calculated_at if observation.run else None) or pattern.get("analysis_date")
        success_count, failure_count = self._pattern_review_counts(pattern.get("analysis_date"))
        marker_summaries = pattern.get("marker_summaries") or []
        success_ready_count = len(marker_summaries)
        contrast_ready_count = sum(int(row.get("failure_training_case_count") or 0) >= PATTERN_REQUIRED_SAMPLE_COUNT for row in marker_summaries)
        pattern_status = "NOT_READY" if not success_ready_count else "READY" if contrast_ready_count == success_ready_count else "PARTIAL"
        reference_date = observation.data_cutoff_date or pattern.get("analysis_date")
        theme_status = self._source_status(observation.data_cutoff_date, reference_date, available=bool(observation_items))
        flow_status = self._source_status(observation.data_cutoff_date, reference_date, available=bool(flow_values))
        realtime_status = self._source_status(realtime.trade_date, reference_date, available=bool(realtime.snapshot_at and realtime.themes))
        market_mode = self._market_mode()
        if market_mode != "POST_MARKET":
            outcome_status = "NOT_READY"
            outcome_note = "장 종료 후 D0 결과를 확인합니다."
        elif not focus_rows or not available_focus:
            outcome_status = "NOT_READY"
            outcome_note = "가격 데이터 최신수집 필요"
        elif len(available_focus) < len(focus_rows) or any(row["outcome"].get("theme_d0_return") is None for row in available_focus):
            outcome_status = "PARTIAL"
            outcome_note = "일부 종목 또는 테마 결과가 준비되지 않았습니다."
        else:
            outcome_status = "READY"
            outcome_note = "종가와 테마 상대성과를 복기에 사용할 수 있습니다."
        if us_error:
            us_status = "ERROR"
        elif not us_observation or not us_observation.summary.linked_count:
            us_status = "NOT_READY"
        elif us_observation.summary.available_count < us_observation.summary.linked_count:
            us_status = "PARTIAL"
        else:
            us_status = self._source_status(us_observation.latest_us_date, reference_date, available=True)
        source_statuses = [theme_status, flow_status, us_status, pattern_status, realtime_status]
        if market_mode == "POST_MARKET":
            source_statuses.append(outcome_status)
        overall_status = "READY" if all(value == "READY" for value in source_statuses) else "NOT_READY" if all(value == "NOT_READY" for value in source_statuses) else "PARTIAL"
        return DrctInsightTodayResponse.model_validate({
            "market_mode": market_mode, "analysis_date": analysis_date,
            "evaluation_captured": evaluation_captured,
            "summary": {"observed_theme_count": len(themes), "preliminary_candidate_count": preliminary_count,
                        "focus_candidate_count": focus_count, "final_candidate_count": final_count,
                        "my_watch_count": len(my_watch), "ready_count": ready_count,
                        "last_updated_at": last_updated},
            "thresholds": {"flow_p25": flow_p25, "flow_median": flow_median,
                           "pattern_edge_p25": edge_p25, "pattern_edge_median": edge_median},
            "freshness": {"domestic_theme": observation.data_cutoff_date,
                          "observation": observation.run.target_date if observation.run else None,
                          "us_kr": us_observation.latest_us_date if us_observation else None,
                          "stock_signal": pattern.get("analysis_date"), "realtime": realtime.snapshot_at},
            "readiness": {
                "overall": overall_status,
                "theme": {"status": theme_status, "source_date": observation.data_cutoff_date,
                          "note": "국내 관찰순위를 Gate 판단에 사용합니다." if observation_items else "관찰순위가 없습니다."},
                "flow": {"status": flow_status, "source_date": observation.data_cutoff_date,
                         "note": "수급점수 분포를 Gate 판단에 사용합니다." if flow_values else "수급점수가 없습니다."},
                "us_kr": {"status": us_status, "source_date": us_observation.latest_us_date if us_observation else None,
                          "note": "기존 오늘의 연계 관찰을 재사용합니다." if us_observation else "한미 연계 계산에 실패했습니다.",
                          "linked_count": us_observation.summary.linked_count if us_observation else 0,
                          "available_count": us_observation.summary.available_count if us_observation else 0,
                          "us_date": us_observation.latest_us_date if us_observation else None,
                          "kr_date": us_observation.kr_target_date if us_observation else None},
                "pattern": {"status": pattern_status, "source_date": pattern.get("analysis_date"),
                            "note": "S/F 비교 가능" if pattern_status == "READY" else "실패 사례 축적 중" if success_ready_count else "성공 사례 축적 중",
                            "success_marker_count": success_count, "failure_marker_count": failure_count,
                            "success_ready_marker_count": success_ready_count,
                            "contrast_ready_marker_count": contrast_ready_count,
                            "failure_shortage_marker_count": max(success_ready_count - contrast_ready_count, 0),
                            "required_sample_count": PATTERN_REQUIRED_SAMPLE_COUNT},
                "realtime": {"status": realtime_status, "source_date": realtime.snapshot_at,
                             "note": "실시간 테마 Snapshot을 사용합니다." if realtime.snapshot_at else "실시간 Snapshot이 없습니다."},
                "outcome": {"status": outcome_status, "source_date": analysis_date, "note": outcome_note},
            },
            "themes": themes, "stocks": stock_rows, "my_watch": my_watch,
            "outcome_summary": outcome_summary, "review_queue": review_queue,
            "storage_policy": "RUNTIME_PLUS_COMPACT_CANDIDATE_HISTORY",
        })

    def capture_today_candidates(self) -> DrctInsightTodayResponse:
        result = self.today()
        if result.market_mode != "POST_MARKET" or not result.analysis_date:
            return result
        rows = [row for row in result.stocks if row.focus_candidate or row.final_candidate]
        if not rows:
            return result
        self._persist_candidate_rows(result.analysis_date, rows)
        captured = result.model_copy(update={"evaluation_captured": True})
        self._publish_today_cache(captured)
        return captured

    def _persist_candidate_rows(self, analysis_date: str, rows: list[Any]) -> None:
        for row in rows:
            self.db.execute(text("""
                INSERT INTO drct_insight_candidate_evaluations
                (analysis_date, stock_id, theme_id, candidate_level, observation_rank,
                 success_similarity, failure_similarity, pattern_edge, user_status, evaluated_at,
                 focus_rank, theme_gate, flow_gate, pattern_status, us_lead_status, insight_rule_version)
                VALUES (:analysis_date, :stock_id, :theme_id, :candidate_level, :observation_rank,
                        :success_similarity, :failure_similarity, :pattern_edge, :user_status, :evaluated_at,
                        :focus_rank, :theme_gate, :flow_gate, :pattern_status, :us_lead_status, :insight_rule_version)
                ON CONFLICT(analysis_date, stock_id) DO UPDATE SET
                    focus_rank=COALESCE(drct_insight_candidate_evaluations.focus_rank, excluded.focus_rank),
                    theme_gate=COALESCE(drct_insight_candidate_evaluations.theme_gate, excluded.theme_gate),
                    flow_gate=COALESCE(drct_insight_candidate_evaluations.flow_gate, excluded.flow_gate),
                    pattern_status=COALESCE(drct_insight_candidate_evaluations.pattern_status, excluded.pattern_status),
                    us_lead_status=COALESCE(drct_insight_candidate_evaluations.us_lead_status, excluded.us_lead_status),
                    insight_rule_version=COALESCE(drct_insight_candidate_evaluations.insight_rule_version, excluded.insight_rule_version),
                    user_status=excluded.user_status,
                    evaluated_at=excluded.evaluated_at
            """), {
                "analysis_date": analysis_date, "stock_id": row.stock_id, "theme_id": row.theme_id,
                "candidate_level": "FINAL" if row.final_candidate else "FOCUS",
                "observation_rank": row.observation_rank, "success_similarity": row.success_similarity,
                "failure_similarity": row.failure_similarity, "pattern_edge": row.pattern_edge,
                "user_status": row.gates.execution or "WAIT", "evaluated_at": now_kst(),
                "focus_rank": row.focus_rank, "theme_gate": row.gates.theme, "flow_gate": row.gates.flow,
                "pattern_status": row.pattern_status,
                "us_lead_status": row.us_lead.strength if row.us_lead.linked else "NONE",
                "insight_rule_version": INSIGHT_RULE_VERSION,
            })
        self.db.commit()
