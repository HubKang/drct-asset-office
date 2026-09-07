from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.app.entities.drct_stock_signal import DrctStockSignalEvent


class DrctSignalPerformanceService:
    """Persist compact operational episodes and evaluate them from local daily prices."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _round(value: float) -> float:
        return round(value, 4)

    def capture(self, scan: dict[str, Any]) -> dict[str, int]:
        analysis_date = scan.get("analysis_date")
        if not analysis_date:
            return {"created": 0, "continued": 0, "closed": 0}
        recording = scan.get("_recording_metadata") or {}
        improvement_pairs = {tuple(pair) for pair in recording.get("improvement_pairs", [])}
        improvement_policy_version = recording.get("improvement_policy_version")
        pairs = {
            (int(stock["stock_id"]), int(signal["marker_id"])): (stock, signal)
            for stock in scan.get("stocks", []) for signal in stock.get("signals", [])
        }
        active = self.db.scalars(select(DrctStockSignalEvent).where(DrctStockSignalEvent.ended_date.is_(None))).all()
        same_day = self.db.scalars(select(DrctStockSignalEvent).where(
            DrctStockSignalEvent.signal_date == str(analysis_date),
        )).all()
        active_by_pair = {(row.stock_id, row.marker_id): row for row in active}
        same_day_by_pair = {(row.stock_id, row.marker_id): row for row in same_day}

        stock_ids = sorted({stock_id for stock_id, _marker_id in pairs})
        d0_close: dict[int, float] = {}
        if stock_ids:
            params: dict[str, Any] = {"analysis_date": str(analysis_date)}
            placeholders = []
            for index, stock_id in enumerate(stock_ids):
                key = f"stock_{index}"
                params[key] = stock_id
                placeholders.append(f":{key}")
            rows = self.db.execute(text(f"""
                SELECT stock_id, close_price FROM stock_daily_prices
                WHERE trade_date=:analysis_date AND stock_id IN ({','.join(placeholders)})
                  AND close_price IS NOT NULL
            """), params).mappings().all()
            d0_close = {int(row["stock_id"]): float(row["close_price"]) for row in rows}

        created = continued = closed = 0
        for pair, (_stock, signal) in pairs.items():
            row = active_by_pair.get(pair) or same_day_by_pair.get(pair)
            if row is not None:
                row.last_seen_date = str(analysis_date)
                row.ended_date = None
                row.updated_at = datetime.now()
                continued += 1
                continue
            close = d0_close.get(pair[0])
            if close is None:
                continue
            algorithm = scan["algorithm"]
            self.db.add(DrctStockSignalEvent(
                stock_id=pair[0], marker_id=pair[1], signal_date=str(analysis_date),
                last_seen_date=str(analysis_date), d0_close=close,
                similarity_score=float(signal["current_pattern_similarity"]),
                similarity_percentile=float(signal["empirical_percentile"]),
                similarity_level=str(signal["candidate_band"]),
                candidate_policy_version=int(algorithm["candidate_policy_version"]),
                pattern_signature_version=int(algorithm["pattern_signature_version"]),
                feature_schema_version=int(algorithm["feature_schema_version"]),
                improvement_candidate=pair in improvement_pairs,
                improvement_policy_version=improvement_policy_version,
                evaluation_status="PENDING",
            ))
            created += 1

        current_pairs = set(pairs)
        for pair, row in active_by_pair.items():
            if pair not in current_pairs:
                row.ended_date = str(analysis_date)
                row.updated_at = datetime.now()
                closed += 1
        self.db.commit()
        return {"created": created, "continued": continued, "closed": closed}

    def refresh(self) -> dict[str, Any]:
        pending = self.db.scalars(select(DrctStockSignalEvent).where(
            DrctStockSignalEvent.evaluation_status != "COMPLETE",
        ).order_by(DrctStockSignalEvent.stock_id, DrctStockSignalEvent.signal_date)).all()
        if pending:
            stock_ids = sorted({row.stock_id for row in pending})
            earliest = min(row.signal_date for row in pending)
            params: dict[str, Any] = {"earliest": earliest}
            placeholders = []
            for index, stock_id in enumerate(stock_ids):
                key = f"stock_{index}"
                params[key] = stock_id
                placeholders.append(f":{key}")
            price_rows = self.db.execute(text(f"""
                SELECT stock_id, trade_date, high_price, low_price, close_price
                FROM stock_daily_prices
                WHERE stock_id IN ({','.join(placeholders)}) AND trade_date>:earliest
                ORDER BY stock_id, trade_date
            """), params).mappings().all()
            prices: dict[int, list[dict[str, Any]]] = defaultdict(list)
            for price in price_rows:
                prices[int(price["stock_id"])].append(dict(price))
            now = datetime.now()
            for event in pending:
                before = (
                    event.evaluation_status, event.d5_date, event.d5_return_pct,
                    event.d10_date, event.d10_return_pct, event.d20_date, event.d20_return_pct,
                    event.max_rise_20_pct, event.max_fall_20_pct,
                )
                future = [row for row in prices[event.stock_id] if str(row["trade_date"])[:10] > event.signal_date]
                if len(future) >= 5 and future[4]["close_price"] is not None:
                    event.d5_date = str(future[4]["trade_date"])[:10]
                    event.d5_return_pct = self._round((float(future[4]["close_price"]) / event.d0_close - 1) * 100)
                if len(future) >= 10 and future[9]["close_price"] is not None:
                    event.d10_date = str(future[9]["trade_date"])[:10]
                    event.d10_return_pct = self._round((float(future[9]["close_price"]) / event.d0_close - 1) * 100)
                if len(future) >= 20:
                    window = future[:20]
                    if all(row["close_price"] is not None and row["high_price"] is not None and row["low_price"] is not None for row in window):
                        event.d20_date = str(window[19]["trade_date"])[:10]
                        event.d20_return_pct = self._round((float(window[19]["close_price"]) / event.d0_close - 1) * 100)
                        event.max_rise_20_pct = self._round((max(float(row["high_price"]) for row in window) / event.d0_close - 1) * 100)
                        event.max_fall_20_pct = self._round((min(float(row["low_price"]) for row in window) / event.d0_close - 1) * 100)
                        event.evaluation_status = "COMPLETE"
                if event.evaluation_status != "COMPLETE":
                    event.evaluation_status = "D10_READY" if event.d10_date else "D5_READY" if event.d5_date else "PENDING"
                after = (
                    event.evaluation_status, event.d5_date, event.d5_return_pct,
                    event.d10_date, event.d10_return_pct, event.d20_date, event.d20_return_pct,
                    event.max_rise_20_pct, event.max_fall_20_pct,
                )
                if after != before:
                    event.evaluated_at = now
                    event.updated_at = now
            self.db.commit()
        return self.summary()

    def summary(self) -> dict[str, Any]:
        overall = self.db.execute(text("""
            SELECT COUNT(*) total_count,
                   SUM(CASE WHEN evaluation_status='COMPLETE' THEN 1 ELSE 0 END) completed_count,
                   AVG(CASE WHEN evaluation_status='COMPLETE' THEN d20_return_pct END) d20_average_pct
            FROM drct_stock_signal_events
        """)).mappings().one()
        markers = self.db.execute(text("""
            SELECT marker.id marker_id, marker.name marker_name, COUNT(event.id) signal_count,
                   SUM(CASE WHEN event.evaluation_status='COMPLETE' THEN 1 ELSE 0 END) completed_count,
                   AVG(event.d5_return_pct) d5_average_pct, AVG(event.d10_return_pct) d10_average_pct,
                   AVG(event.d20_return_pct) d20_average_pct,
                   AVG(event.max_rise_20_pct) max_rise_average_pct,
                   AVG(event.max_fall_20_pct) max_fall_average_pct
            FROM drct_stock_signal_events event
            JOIN chart_markers marker ON marker.id=event.marker_id
            GROUP BY marker.id, marker.name, marker.sort_order
            ORDER BY marker.sort_order, marker.name
        """)).mappings().all()
        total = int(overall["total_count"] or 0)
        completed = int(overall["completed_count"] or 0)
        return {
            "total_count": total, "completed_count": completed, "pending_count": total - completed,
            "d20_average_pct": self._nullable_round(overall["d20_average_pct"]),
            "markers": [{key: self._nullable_round(value) if key.endswith("_pct") else value
                         for key, value in dict(row).items()} for row in markers],
            "refreshed_at": datetime.now(),
        }

    @staticmethod
    def _nullable_round(value: Any) -> float | None:
        return None if value is None else round(float(value), 4)

    def events(self, period_days: int | None = None, marker_id: int | None = None, query: str | None = None) -> dict[str, Any]:
        clauses = ["1=1"]
        params: dict[str, Any] = {}
        if period_days is not None:
            clauses.append("event.signal_date>=:start_date")
            params["start_date"] = (date.today() - timedelta(days=period_days)).isoformat()
        if marker_id is not None:
            clauses.append("event.marker_id=:marker_id")
            params["marker_id"] = marker_id
        if query and query.strip():
            clauses.append("(stock.stock_name LIKE :query OR stock.stock_code LIKE :query)")
            params["query"] = f"%{query.strip()}%"
        where = " AND ".join(clauses)
        rows = self.db.execute(text(f"""
            SELECT event.*, COUNT(*) OVER() total_count, stock.stock_code, stock.stock_name, marker.name marker_name,
                   marker.symbol marker_symbol, marker_group.name marker_group_name,
                   marker_group.color marker_group_color
            FROM drct_stock_signal_events event
            JOIN stocks stock ON stock.id=event.stock_id
            JOIN chart_markers marker ON marker.id=event.marker_id
            JOIN chart_marker_groups marker_group ON marker_group.id=marker.marker_group_id
            WHERE {where}
            ORDER BY event.signal_date DESC, event.id DESC
            LIMIT 500
        """), params).mappings().all()
        return {"total": int(rows[0]["total_count"]) if rows else 0, "items": [self._event_item(row) for row in rows]}

    def detail(self, event_id: int) -> dict[str, Any]:
        row = self.db.execute(text("""
            SELECT event.*, stock.stock_code, stock.stock_name, marker.name marker_name,
                   marker.symbol marker_symbol, marker_group.name marker_group_name,
                   marker_group.color marker_group_color
            FROM drct_stock_signal_events event
            JOIN stocks stock ON stock.id=event.stock_id
            JOIN chart_markers marker ON marker.id=event.marker_id
            JOIN chart_marker_groups marker_group ON marker_group.id=marker.marker_group_id
            WHERE event.id=:event_id
        """), {"event_id": event_id}).mappings().one_or_none()
        if row is None:
            raise HTTPException(404, "시그널 성과 기록을 찾을 수 없습니다.")
        return {**self._event_item(row), "d0_close": float(row["d0_close"])}

    @staticmethod
    def _event_item(row: Any) -> dict[str, Any]:
        keys = (
            "id", "stock_id", "stock_code", "stock_name", "marker_id", "marker_name", "marker_symbol",
            "marker_group_name", "marker_group_color", "signal_date", "last_seen_date", "ended_date",
            "similarity_score", "evaluation_status", "d5_date", "d5_return_pct", "d10_date",
            "d10_return_pct", "d20_date", "d20_return_pct", "max_rise_20_pct", "max_fall_20_pct", "evaluated_at",
        )
        return {key: row[key] for key in keys}
