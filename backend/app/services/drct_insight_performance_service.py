from __future__ import annotations

from collections import defaultdict
from math import ceil
from statistics import mean, median
from typing import Any, Callable

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.schemas.drct_insight_schema import (
    DrctInsightPerformanceRefreshResponse,
    DrctInsightPerformanceResponse,
)
from backend.app.services.drct_future_outcome_service import FutureOutcomeService
from backend.app.core.config import now_kst


class DrctInsightPerformanceService:
    """Live candidate evaluation only; prices stay in stock_daily_prices."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _bind(prefix: str, values: list[int]) -> tuple[str, dict[str, int]]:
        params = {f"{prefix}_{index}": value for index, value in enumerate(values)}
        return ",".join(f":{key}" for key in params), params

    def refresh(self, force: bool = False) -> DrctInsightPerformanceRefreshResponse:
        candidates = self.db.execute(text(f"""
            SELECT id, analysis_date, stock_id, d0_return, d1_return, d3_return, d5_return,
                   mfe_5d, mae_5d, outcome_status
            FROM drct_insight_candidate_evaluations
            {"" if force else "WHERE COALESCE(outcome_status,'PENDING')<>'COMPLETE'"}
            ORDER BY analysis_date DESC, id DESC
        """)).mappings().all()
        evaluated_at = now_kst()
        if not candidates:
            counts = self._status_counts()
            return DrctInsightPerformanceRefreshResponse(
                target_count=0, updated_count=0, evaluated_at=evaluated_at, **counts
            )

        stock_ids = sorted({int(row["stock_id"]) for row in candidates})
        stock_clause, stock_params = self._bind("stock", stock_ids)
        earliest = min(str(row["analysis_date"])[:10] for row in candidates)
        price_rows = self.db.execute(text(f"""
            SELECT stock_id, trade_date, high_price, low_price, close_price, change_rate
            FROM stock_daily_prices
            WHERE stock_id IN ({stock_clause}) AND trade_date>=:earliest
            ORDER BY stock_id, trade_date
        """), {**stock_params, "earliest": earliest}).mappings().all()
        prices: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in price_rows:
            prices[int(row["stock_id"])].append(dict(row))

        updated = 0
        for candidate in candidates:
            rows = prices.get(int(candidate["stock_id"]), [])
            d0_date = str(candidate["analysis_date"])[:10]
            d0_index = next((index for index, row in enumerate(rows) if str(row["trade_date"])[:10] == d0_date), None)
            d0_row = rows[d0_index] if d0_index is not None else None
            d0_close = float(d0_row["close_price"]) if d0_row and d0_row.get("close_price") not in (None, 0) else None
            future = rows[d0_index + 1:d0_index + 6] if d0_index is not None else []
            outcome = FutureOutcomeService.calculate_horizons(d0_close, future, (1, 3, 5), 5)
            d0_return = float(d0_row["change_rate"]) if d0_row and d0_row.get("change_rate") is not None else None
            if outcome["d1_return"] is None:
                status = "PENDING"
            elif outcome["d5_return"] is not None and outcome["mfe_5"] is not None and outcome["mae_5"] is not None:
                status = "COMPLETE"
            else:
                status = "PARTIAL"
            next_values = (
                self._round(d0_return), self._round(outcome["d1_return"]), self._round(outcome["d3_return"]),
                self._round(outcome["d5_return"]), self._round(outcome["mfe_5"]), self._round(outcome["mae_5"]), status,
            )
            before = tuple(candidate[key] for key in ("d0_return", "d1_return", "d3_return", "d5_return", "mfe_5d", "mae_5d", "outcome_status"))
            if before != next_values:
                updated += 1
            self.db.execute(text("""
                UPDATE drct_insight_candidate_evaluations
                SET d0_return=:d0, d1_return=:d1, d3_return=:d3, d5_return=:d5,
                    mfe_5d=:mfe, mae_5d=:mae, outcome_status=:status,
                    outcome_evaluated_at=:evaluated_at
                WHERE id=:id
            """), {
                "id": candidate["id"], "d0": next_values[0], "d1": next_values[1], "d3": next_values[2],
                "d5": next_values[3], "mfe": next_values[4], "mae": next_values[5],
                "status": status, "evaluated_at": evaluated_at,
            })
        self.db.commit()
        return DrctInsightPerformanceRefreshResponse(
            target_count=len(candidates), updated_count=updated, evaluated_at=evaluated_at, **self._status_counts()
        )

    def evaluations(
        self,
        period: str = "60",
        candidate_level: str | None = None,
        theme_id: int | None = None,
        pattern_status: str | None = None,
        outcome_status: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> DrctInsightPerformanceResponse:
        clauses = ["1=1"]
        params: dict[str, Any] = {}
        cutoff = self._trading_cutoff(period)
        if cutoff:
            clauses.append("evaluation.analysis_date>=:cutoff")
            params["cutoff"] = cutoff
        if candidate_level:
            clauses.append("evaluation.candidate_level=:candidate_level")
            params["candidate_level"] = candidate_level
        if theme_id is not None:
            clauses.append("evaluation.theme_id=:theme_id")
            params["theme_id"] = theme_id
        if pattern_status:
            clauses.append("evaluation.pattern_status=:pattern_status")
            params["pattern_status"] = pattern_status
        if outcome_status:
            clauses.append("COALESCE(evaluation.outcome_status,'PENDING')=:outcome_status")
            params["outcome_status"] = outcome_status
        where = " AND ".join(clauses)
        rows = self.db.execute(text(f"""
            WITH marker_ranked AS (
                SELECT event.id, event.stock_id, event.marker_date, event.review_result,
                       ROW_NUMBER() OVER (PARTITION BY event.stock_id, event.marker_date
                                          ORDER BY event.reviewed_at DESC, event.id DESC) rn
                FROM chart_marker_events event
            )
            SELECT evaluation.*, stock.stock_code, stock.stock_name, theme.theme_name,
                   marker.id marker_event_id, marker.review_result marker_review_result
            FROM drct_insight_candidate_evaluations evaluation
            JOIN stocks stock ON stock.id=evaluation.stock_id
            LEFT JOIN market_themes theme ON theme.id=evaluation.theme_id
            LEFT JOIN marker_ranked marker ON marker.stock_id=evaluation.stock_id
                  AND marker.marker_date=evaluation.analysis_date AND marker.rn=1
            WHERE {where}
            ORDER BY evaluation.analysis_date DESC, COALESCE(evaluation.focus_rank,999), evaluation.id DESC
        """), params).mappings().all()
        items = [self._item(dict(row)) for row in rows]
        items.sort(key=self._performance_sort_key)
        start = (page - 1) * page_size
        themes = self.db.execute(text("""
            SELECT DISTINCT theme.id, theme.theme_name
            FROM drct_insight_candidate_evaluations evaluation
            JOIN market_themes theme ON theme.id=evaluation.theme_id
            ORDER BY theme.theme_name
        """)).mappings().all()
        return DrctInsightPerformanceResponse.model_validate({
            "page": page, "page_size": page_size, "total": len(items),
            "total_pages": max(ceil(len(items) / page_size), 1), "period": period,
            "items": items[start:start + page_size],
            "themes": [{"id": int(row["id"]), "name": str(row["theme_name"])} for row in themes],
            "summary": self._summary(items), "groups": self._groups(items),
            "latest_evaluated_at": max((row.get("outcome_evaluated_at") for row in items if row.get("outcome_evaluated_at")), default=None),
        })

    def _trading_cutoff(self, period: str) -> str | None:
        if period == "ALL":
            return None
        rows = self.db.execute(text("""
            SELECT DISTINCT trade_date FROM stock_daily_prices
            ORDER BY trade_date DESC LIMIT :period
        """), {"period": int(period)}).scalars().all()
        return str(rows[-1])[:10] if rows else None

    def _status_counts(self) -> dict[str, int]:
        row = self.db.execute(text("""
            SELECT SUM(CASE WHEN COALESCE(outcome_status,'PENDING')='PENDING' THEN 1 ELSE 0 END) pending_count,
                   SUM(CASE WHEN outcome_status='PARTIAL' THEN 1 ELSE 0 END) partial_count,
                   SUM(CASE WHEN outcome_status='COMPLETE' THEN 1 ELSE 0 END) complete_count
            FROM drct_insight_candidate_evaluations
        """)).mappings().one()
        return {key: int(row[key] or 0) for key in ("pending_count", "partial_count", "complete_count")}

    @staticmethod
    def _round(value: Any) -> float | None:
        return None if value is None else round(float(value), 4)

    @staticmethod
    def _performance_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
        def outcome(value: Any) -> tuple[int, float]:
            return (1, 0.0) if value is None else (0, -float(value))

        date_key = -int(str(row.get("analysis_date") or "0000-00-00").replace("-", "")[:8])
        focus_rank = int(row.get("focus_rank") or 999999)
        return (
            *outcome(row.get("mfe_5d")),
            *outcome(row.get("d5_return")),
            *outcome(row.get("d3_return")),
            *outcome(row.get("d1_return")),
            *outcome(row.get("d0_return")),
            date_key,
            focus_rank,
            -int(row.get("id") or 0),
        )

    @classmethod
    def _item(cls, row: dict[str, Any]) -> dict[str, Any]:
        marker = row.pop("marker_review_result", None)
        row["marker_status"] = str(marker) if marker in {"S", "F"} else "UNDECIDED" if row.get("marker_event_id") else "UNRECORDED"
        row["outcome_status"] = row.get("outcome_status") or "PENDING"
        return row

    @classmethod
    def _metric(cls, rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
        values = [float(row[key]) for row in rows if row.get(key) is not None]
        return {
            "n": len(values), "positive_ratio": round(sum(value > 0 for value in values) / len(values) * 100, 4) if values else None,
            "mean": round(mean(values), 4) if values else None, "median": round(median(values), 4) if values else None,
        }

    @classmethod
    def _summary(cls, rows: list[dict[str, Any]]) -> dict[str, Any]:
        statuses = [row["outcome_status"] for row in rows]
        marker_counts = {key: sum(row["marker_status"] == key for row in rows) for key in ("S", "F", "UNDECIDED", "UNRECORDED")}
        return {
            "total_count": len(rows), "pending_count": statuses.count("PENDING"),
            "partial_count": statuses.count("PARTIAL"), "complete_count": statuses.count("COMPLETE"),
            "d0": cls._metric(rows, "d0_return"), "d1": cls._metric(rows, "d1_return"),
            "d3": cls._metric(rows, "d3_return"), "d5": cls._metric(rows, "d5_return"),
            "mfe_5d": cls._metric(rows, "mfe_5d"), "mae_5d": cls._metric(rows, "mae_5d"),
            "marker_counts": marker_counts,
        }

    @classmethod
    def _group_rows(cls, rows: list[dict[str, Any]], key_fn: Callable[[dict[str, Any]], tuple[str, str]]) -> list[dict[str, Any]]:
        grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[key_fn(row)].append(row)
        result = []
        for (key, label), selected in grouped.items():
            d5 = cls._metric(selected, "d5_return")
            result.append({
                "key": key, "label": label, "n": len(selected),
                "sample_status": "ENOUGH" if d5["n"] >= 5 and "UNKNOWN" not in key else "INSUFFICIENT",
                "d5": d5, "mfe_5d": cls._metric(selected, "mfe_5d"),
                "mae_5d": cls._metric(selected, "mae_5d"),
            })
        return sorted(result, key=lambda item: item["key"])

    @classmethod
    def _groups(cls, rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        def observation(row: dict[str, Any]) -> tuple[str, str]:
            value = row.get("observation_rank")
            if value is None: return "99_UNKNOWN", "미확인"
            if value <= 5: return "01_1_5", "Rank 1~5"
            if value <= 10: return "02_6_10", "Rank 6~10"
            if value <= 20: return "03_11_20", "Rank 11~20"
            return "04_21_PLUS", "Rank 21+"

        def similarity(row: dict[str, Any]) -> tuple[str, str]:
            value = row.get("success_similarity")
            if value is None: return "99_UNKNOWN", "미확인"
            if value < 60: return "01_LT60", "성공 유사도 60 미만"
            if value < 70: return "02_60_69", "성공 유사도 60~69"
            if value < 80: return "03_70_79", "성공 유사도 70~79"
            return "04_80_PLUS", "성공 유사도 80 이상"

        def focus_rank(row: dict[str, Any]) -> tuple[str, str]:
            value = row.get("focus_rank")
            if value is None: return "99_UNKNOWN", "미확인"
            return ("01_TOP3", "Focus 1~3") if value <= 3 else ("02_4_8", "Focus 4~8")

        edge_rows = [row for row in rows if row.get("pattern_edge") is not None]
        edge_groups = cls._group_rows(edge_rows, lambda row: ("01_NEGATIVE", "Edge < 0") if row["pattern_edge"] < 0 else ("02_LOW", "Edge 0~9") if row["pattern_edge"] < 10 else ("03_HIGH", "Edge 10+"))
        if not edge_groups:
            empty = {"n": 0, "positive_ratio": None, "mean": None, "median": None}
            edge_groups = [{"key": "ACCUMULATING", "label": "데이터 축적 중", "n": 0, "sample_status": "ACCUMULATING", "d5": empty, "mfe_5d": empty, "mae_5d": empty}]
        return {
            "flow": cls._group_rows(rows, lambda row: (str(row.get("flow_gate") or "UNKNOWN"), str(row.get("flow_gate") or "미확인"))),
            "us_lead": cls._group_rows(rows, lambda row: ("STRONG", "US Lead 강") if row.get("us_lead_status") == "STRONG" else ("NORMAL", "US Lead 보통") if row.get("us_lead_status") in {"MODERATE", "WEAK"} else ("NONE", "US Lead 없음") if row.get("us_lead_status") == "NONE" else ("UNKNOWN", "미확인")),
            "observation_rank": cls._group_rows(rows, observation),
            "success_similarity": cls._group_rows(rows, similarity),
            "focus_rank": cls._group_rows(rows, focus_rank),
            "pattern_edge": edge_groups,
        }
