from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.market_calendar_schema import (
    MarketCalendarDailyResponse,
    MarketCalendarEventCreateRequest,
    MarketCalendarEventResponse,
    MarketCalendarEventUpdateRequest,
    MarketCalendarMonthlyResponse,
)
from backend.app.services.market_calendar_service import MarketCalendarService

router = APIRouter()


@router.get("/market-calendar/events/monthly", response_model=MarketCalendarMonthlyResponse)
def list_monthly_calendar_events(
    month: str = Query(..., min_length=7, max_length=7),
    theme_group_id: int | None = Query(default=None),
    theme_id: int | None = Query(default=None),
    keyword: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> MarketCalendarMonthlyResponse:
    return MarketCalendarService(db).list_monthly(
        month=month,
        theme_group_id=theme_group_id,
        theme_id=theme_id,
        keyword=keyword,
        event_type=event_type,
    )


@router.get("/market-calendar/events/daily", response_model=MarketCalendarDailyResponse)
def list_daily_calendar_events(
    date: str = Query(..., min_length=10, max_length=10),
    db: Session = Depends(get_db),
) -> MarketCalendarDailyResponse:
    return MarketCalendarService(db).list_daily(date)


@router.post("/market-calendar/events", response_model=MarketCalendarEventResponse)
def create_calendar_event(
    payload: MarketCalendarEventCreateRequest,
    db: Session = Depends(get_db),
) -> MarketCalendarEventResponse:
    return MarketCalendarService(db).create_event(payload)


@router.put("/market-calendar/events/{event_id}", response_model=MarketCalendarEventResponse)
def update_calendar_event(
    event_id: int,
    payload: MarketCalendarEventUpdateRequest,
    db: Session = Depends(get_db),
) -> MarketCalendarEventResponse:
    return MarketCalendarService(db).update_event(event_id, payload)


@router.delete("/market-calendar/events/{event_id}")
def delete_calendar_event(event_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    return MarketCalendarService(db).delete_event(event_id)
