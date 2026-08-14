from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.chart_marker_schema import MarkerEventPatch, MarkerEventWrite, MarkerGroupPatch, MarkerGroupWrite, MarkerPatch, MarkerWrite
from backend.app.services.chart_marker_service import ChartMarkerService

router = APIRouter(prefix="/chart-markers", tags=["chart-markers"])

@router.get("/catalog")
def catalog(active_only: bool = False, db: Session = Depends(get_db)): return ChartMarkerService(db).list_catalog(active_only)
@router.post("/groups", status_code=201)
def create_group(payload: MarkerGroupWrite, db: Session = Depends(get_db)): return ChartMarkerService(db).create_group(payload)
@router.patch("/groups/{group_id}")
def update_group(group_id: int, payload: MarkerGroupPatch, db: Session = Depends(get_db)): return ChartMarkerService(db).update_group(group_id, payload)
@router.post("/markers", status_code=201)
def create_marker(payload: MarkerWrite, db: Session = Depends(get_db)): return ChartMarkerService(db).create_marker(payload)
@router.patch("/markers/{marker_id}")
def update_marker(marker_id: int, payload: MarkerPatch, db: Session = Depends(get_db)): return ChartMarkerService(db).update_marker(marker_id, payload)
@router.put("/events")
def upsert_event(payload: MarkerEventWrite, db: Session = Depends(get_db)): return ChartMarkerService(db).upsert_event(payload)
@router.get("/events")
def stock_events(stock_id: int, end_date: date | None = None, db: Session = Depends(get_db)): return ChartMarkerService(db).list_stock_events(stock_id, end_date)
@router.patch("/events/{event_id}")
def update_event(event_id: int, payload: MarkerEventPatch, db: Session = Depends(get_db)): return ChartMarkerService(db).update_event(event_id, payload)
@router.delete("/events/{event_id}")
def delete_event(event_id: int, db: Session = Depends(get_db)): return ChartMarkerService(db).delete_event(event_id)
@router.get("/review/events")
def review_events(marker_id: int, db: Session = Depends(get_db)): return ChartMarkerService(db).review_events(marker_id)
@router.get("/review/chart")
def review_chart(stock_id: int, marker_date: date, candle_count: int = Query(81, ge=3, le=201), db: Session = Depends(get_db)):
    return ChartMarkerService(db).review_chart(stock_id, marker_date, candle_count)
