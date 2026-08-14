from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.entities.chart_marker import ChartMarker, ChartMarkerEvent, ChartMarkerGroup
from backend.app.schemas.chart_marker_schema import MarkerEventPatch, MarkerEventWrite, MarkerGroupPatch, MarkerGroupWrite, MarkerPatch, MarkerWrite


class ChartMarkerService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _group(row: ChartMarkerGroup) -> dict[str, Any]:
        return {"id": row.id, "name": row.name, "description": row.description, "color": row.color,
                "sort_order": row.sort_order, "is_active": row.is_active, "created_at": row.created_at, "updated_at": row.updated_at}

    @staticmethod
    def _marker(
        row: ChartMarker,
        stock_count: int = 0,
        marker_count: int = 0,
        success_count: int = 0,
        failure_count: int = 0,
    ) -> dict[str, Any]:
        return {"id": row.id, "marker_group_id": row.marker_group_id, "name": row.name, "description": row.description,
                "symbol": row.symbol, "sort_order": row.sort_order, "is_active": row.is_active,
                "stock_count": stock_count, "marker_count": marker_count,
                "success_count": success_count, "failure_count": failure_count,
                "created_at": row.created_at, "updated_at": row.updated_at}

    def list_catalog(self, active_only: bool = False) -> dict[str, Any]:
        groups = self.db.scalars(select(ChartMarkerGroup).order_by(ChartMarkerGroup.sort_order, ChartMarkerGroup.name)).all()
        markers = self.db.scalars(select(ChartMarker).order_by(ChartMarker.sort_order, ChartMarker.name)).all()
        count_rows = self.db.execute(text("""SELECT marker_id, COUNT(DISTINCT stock_id) stock_count, COUNT(*) marker_count,
            SUM(CASE WHEN review_result='SUCCESS' THEN 1 ELSE 0 END) success_count,
            SUM(CASE WHEN review_result='FAILURE' THEN 1 ELSE 0 END) failure_count
            FROM chart_marker_events GROUP BY marker_id""")).all()
        counts = {row.marker_id: (row.stock_count, row.marker_count, row.success_count, row.failure_count) for row in count_rows}
        result = []
        for group in groups:
            if active_only and not group.is_active:
                continue
            item = self._group(group)
            item["markers"] = [self._marker(marker, *counts.get(marker.id, (0, 0, 0, 0))) for marker in markers if marker.marker_group_id == group.id and (not active_only or marker.is_active)]
            result.append(item)
        return {"items": result}

    def create_group(self, payload: MarkerGroupWrite) -> dict[str, Any]:
        row = ChartMarkerGroup(**payload.model_dump())
        self.db.add(row)
        self._commit_unique("같은 이름의 마커그룹이 이미 있습니다.")
        self.db.refresh(row)
        return self._group(row)

    def update_group(self, group_id: int, payload: MarkerGroupPatch) -> dict[str, Any]:
        row = self.db.get(ChartMarkerGroup, group_id)
        if not row:
            raise HTTPException(404, "마커그룹을 찾을 수 없습니다.")
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(row, key, value)
        self._commit_unique("같은 이름의 마커그룹이 이미 있습니다.")
        self.db.refresh(row)
        return self._group(row)

    def create_marker(self, payload: MarkerWrite) -> dict[str, Any]:
        if not self.db.get(ChartMarkerGroup, payload.marker_group_id):
            raise HTTPException(404, "마커그룹을 찾을 수 없습니다.")
        row = ChartMarker(**payload.model_dump())
        self.db.add(row)
        self._commit_unique("이 그룹에 같은 이름의 마커가 이미 있습니다.")
        self.db.refresh(row)
        return self._marker(row)

    def update_marker(self, marker_id: int, payload: MarkerPatch) -> dict[str, Any]:
        row = self.db.get(ChartMarker, marker_id)
        if not row:
            raise HTTPException(404, "차트마커를 찾을 수 없습니다.")
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(row, key, value)
        self._commit_unique("이 그룹에 같은 이름의 마커가 이미 있습니다.")
        self.db.refresh(row)
        return self._marker(row)

    def upsert_event(self, payload: MarkerEventWrite) -> dict[str, Any]:
        marker = self.db.get(ChartMarker, payload.marker_id)
        if not marker or not marker.is_active:
            raise HTTPException(400, "활성 차트마커를 선택해 주세요.")
        stock = self.db.execute(text("SELECT id FROM stocks WHERE id = :id"), {"id": payload.stock_id}).first()
        if not stock:
            raise HTTPException(404, "종목을 찾을 수 없습니다.")
        price = self.db.execute(text("SELECT 1 FROM stock_daily_prices WHERE stock_id=:stock_id AND trade_date=:marker_date"),
                                {"stock_id": payload.stock_id, "marker_date": payload.marker_date.isoformat()}).first()
        if not price:
            raise HTTPException(400, "해당 날짜의 종목 가격 데이터가 없습니다.")
        row = self.db.scalar(select(ChartMarkerEvent).where(ChartMarkerEvent.stock_id == payload.stock_id,
            ChartMarkerEvent.marker_id == payload.marker_id, ChartMarkerEvent.marker_date == payload.marker_date))
        created = row is None
        if row is None:
            row = ChartMarkerEvent(**payload.model_dump())
            self.db.add(row)
        else:
            row.memo = payload.memo
        self.db.commit()
        self.db.refresh(row)
        return {**self._event_detail(row), "created": created}

    def list_stock_events(self, stock_id: int, end_date: date | None = None) -> dict[str, Any]:
        sql = """
            SELECT e.id, e.stock_id, e.marker_id, e.marker_date, e.memo, e.review_result, e.reviewed_at, e.created_at, e.updated_at,
                   m.name marker_name, m.symbol, g.id marker_group_id, g.name group_name, g.color group_color
            FROM chart_marker_events e JOIN chart_markers m ON m.id=e.marker_id
            JOIN chart_marker_groups g ON g.id=m.marker_group_id WHERE e.stock_id=:stock_id
        """
        params: dict[str, Any] = {"stock_id": stock_id}
        if end_date:
            sql += " AND e.marker_date <= :end_date"
            params["end_date"] = end_date.isoformat()
        sql += " ORDER BY e.marker_date, g.sort_order, m.sort_order, e.id"
        return {"items": [dict(row._mapping) for row in self.db.execute(text(sql), params)]}

    def update_event(self, event_id: int, payload: MarkerEventPatch) -> dict[str, Any]:
        row = self.db.get(ChartMarkerEvent, event_id)
        if not row:
            raise HTTPException(404, "차트마커 기록을 찾을 수 없습니다.")
        changes = payload.model_dump(exclude_unset=True)
        if "memo" in changes:
            row.memo = changes["memo"]
        if "review_result" in changes:
            row.review_result = changes["review_result"]
            row.reviewed_at = datetime.now() if row.review_result else None
        self.db.commit(); self.db.refresh(row)
        return self._event_detail(row)

    def delete_event(self, event_id: int) -> dict[str, Any]:
        row = self.db.get(ChartMarkerEvent, event_id)
        if not row:
            raise HTTPException(404, "차트마커 기록을 찾을 수 없습니다.")
        self.db.delete(row); self.db.commit()
        return {"deleted": True, "id": event_id}

    def review_events(self, marker_id: int) -> dict[str, Any]:
        rows = self.db.execute(text("""
            SELECT e.id, e.stock_id, s.stock_code, s.stock_name, e.marker_id, e.marker_date, e.memo,
                   e.review_result, e.reviewed_at,
                   m.name marker_name, m.symbol, g.id marker_group_id, g.name group_name, g.color group_color
            FROM chart_marker_events e JOIN stocks s ON s.id=e.stock_id JOIN chart_markers m ON m.id=e.marker_id
            JOIN chart_marker_groups g ON g.id=m.marker_group_id WHERE e.marker_id=:marker_id
            ORDER BY s.stock_name COLLATE NOCASE ASC, e.marker_date DESC
        """), {"marker_id": marker_id}).all()
        return {"items": [dict(row._mapping) for row in rows]}

    def review_chart(self, stock_id: int, marker_date: date, candle_count: int = 81) -> dict[str, Any]:
        params = {"stock_id": stock_id, "marker_date": marker_date.isoformat(), "side_limit": max(0, candle_count - 1)}
        center = self.db.execute(text("SELECT * FROM stock_daily_prices WHERE stock_id=:stock_id AND trade_date=:marker_date"), params).first()
        if not center:
            return {"stock_id": stock_id, "marker_date": marker_date, "marker_index": None, "total_candles": 0,
                    "available_before": 0, "available_after": 0, "candles": []}

        before_available = self.db.execute(text("""SELECT * FROM stock_daily_prices WHERE stock_id=:stock_id AND trade_date < :marker_date
            ORDER BY trade_date DESC LIMIT :side_limit"""), params).all()
        after_available = self.db.execute(text("""SELECT * FROM stock_daily_prices WHERE stock_id=:stock_id AND trade_date > :marker_date
            ORDER BY trade_date ASC LIMIT :side_limit"""), params).all()
        target_before = candle_count // 2
        target_after = candle_count - target_before - 1
        before_count = min(target_before, len(before_available))
        after_count = min(target_after, len(after_available))

        before_rows = before_available[:before_count][::-1]
        after_rows = after_available[:after_count]
        rows = [*before_rows, center, *after_rows]
        candles = [{"trade_date": r.trade_date, "open": r.open_price, "high": r.high_price, "low": r.low_price,
                    "close": r.close_price, "volume": r.volume, "moving_averages": {f"ma{n}": getattr(r, f"ma{n}") for n in (5,10,20,60,120)}} for r in rows]
        return {"stock_id": stock_id, "marker_date": marker_date, "marker_index": len(before_rows),
                "total_candles": len(candles), "available_before": len(before_rows),
                "available_after": len(after_rows), "candles": candles}

    def _event_detail(self, row: ChartMarkerEvent) -> dict[str, Any]:
        marker = self.db.get(ChartMarker, row.marker_id); group = self.db.get(ChartMarkerGroup, marker.marker_group_id) if marker else None
        return {"id": row.id, "stock_id": row.stock_id, "marker_id": row.marker_id, "marker_date": row.marker_date,
                "memo": row.memo, "review_result": row.review_result, "reviewed_at": row.reviewed_at,
                "marker_name": marker.name if marker else "", "symbol": marker.symbol if marker else "",
                "marker_group_id": group.id if group else None, "group_name": group.name if group else "", "group_color": group.color if group else "#64748b",
                "created_at": row.created_at, "updated_at": row.updated_at}

    def _commit_unique(self, message: str) -> None:
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(409, message) from exc
