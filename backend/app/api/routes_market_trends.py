from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.market_trend_schema import (
    AssignThemeToTrendEventRequest,
    AssignThemeToTrendEventResponse,
    CollectMarketPriceSnapshotsRequest,
    CollectMarketPriceSnapshotsResponse,
    CollectMarketTrendEventsRequest,
    CollectMarketTrendEventsResponse,
    DailyThemeFlowResponse,
    DetectEventsFromSnapshotRequest,
    DetectEventsFromSnapshotResponse,
    MarketPriceSnapshotResponse,
    MarketTrendEventResponse,
    TrendDetectionSettingResponse,
    TrendDetectionSettingUpdateRequest,
)
from backend.app.services.market_trend_service import MarketTrendService

router = APIRouter()


@router.get("/market-trends/detection-settings", response_model=TrendDetectionSettingResponse)
def get_market_trend_detection_settings(db: Session = Depends(get_db)) -> TrendDetectionSettingResponse:
    return MarketTrendService(db).get_detection_settings()


@router.put("/market-trends/detection-settings", response_model=TrendDetectionSettingResponse)
def update_market_trend_detection_settings(
    payload: TrendDetectionSettingUpdateRequest,
    db: Session = Depends(get_db),
) -> TrendDetectionSettingResponse:
    return MarketTrendService(db).update_detection_settings(payload)


@router.post("/market-trends/events/collect", response_model=CollectMarketTrendEventsResponse)
def collect_market_trend_events(
    payload: CollectMarketTrendEventsRequest,
    db: Session = Depends(get_db),
) -> CollectMarketTrendEventsResponse:
    return MarketTrendService(db).collect_events(payload.trade_date)


@router.post("/market-trends/snapshots/collect", response_model=CollectMarketPriceSnapshotsResponse)
def collect_market_trend_snapshots(
    payload: CollectMarketPriceSnapshotsRequest,
    db: Session = Depends(get_db),
) -> CollectMarketPriceSnapshotsResponse:
    return MarketTrendService(db).collect_snapshots(
        payload.snapshot_date,
        payload.market_scope,
        payload.collect_mode,
        payload.limit,
    )


@router.get("/market-trends/snapshots", response_model=list[MarketPriceSnapshotResponse])
def list_market_trend_snapshots(
    market_scope: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    sort_order: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[MarketPriceSnapshotResponse]:
    return MarketTrendService(db).list_snapshots(
        market_scope=market_scope,
        keyword=keyword,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
    )


@router.post("/market-trends/events/detect-from-snapshot", response_model=DetectEventsFromSnapshotResponse)
def detect_market_trend_events_from_snapshot(
    payload: DetectEventsFromSnapshotRequest,
    db: Session = Depends(get_db),
) -> DetectEventsFromSnapshotResponse:
    return MarketTrendService(db).detect_events_from_snapshot(payload.snapshot_date)


@router.get("/market-trends/events", response_model=list[MarketTrendEventResponse])
def list_market_trend_events(
    trade_date: str | None = Query(default=None),
    theme_status: str | None = Query(default=None),
    theme_id: int | None = Query(default=None),
    market_scope: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[MarketTrendEventResponse]:
    return MarketTrendService(db).list_events(
        trade_date=trade_date,
        theme_status=theme_status,
        theme_id=theme_id,
        market_scope=market_scope,
        limit=limit,
        offset=offset,
    )


@router.patch("/market-trends/events/{event_id}/theme", response_model=AssignThemeToTrendEventResponse)
def assign_market_trend_event_theme(
    event_id: int,
    payload: AssignThemeToTrendEventRequest,
    db: Session = Depends(get_db),
) -> AssignThemeToTrendEventResponse:
    return MarketTrendService(db).assign_event_theme(event_id, payload)


@router.get("/market-trends/daily-theme-flow", response_model=DailyThemeFlowResponse)
def get_market_trend_daily_theme_flow(
    trade_date: str | None = Query(default=None),
    only_supply_theme: bool = Query(default=False),
    market_scope: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> DailyThemeFlowResponse:
    return MarketTrendService(db).get_daily_theme_flow(
        trade_date=trade_date,
        only_supply_theme=only_supply_theme,
        market_scope=market_scope,
    )
