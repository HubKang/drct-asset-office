from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.external_kiwoom_schema import (
    KiwoomConditionListResponse,
    KiwoomConditionResultListResponse,
    KiwoomConditionPreviewRequest,
    KiwoomConditionPreviewResponse,
    KiwoomConditionResultSaveRequest,
    KiwoomConditionResultSaveResponse,
    KiwoomConditionSyncRequest,
    KiwoomConditionSyncResponse,
    KiwoomConditionRefreshResponse,
    KiwoomMarketEventDeleteResponse,
    KiwoomMarketEventListResponse,
    KiwoomMarketEventPatchRequest,
    KiwoomMarketEventPatchResponse,
    KiwoomMarketEventThemeLinkAddRequest,
    KiwoomMarketEventThemeLinkAddResponse,
    KiwoomMarketEventThemeLinkDeleteResponse,
    KiwoomMarketEventThemeLinkListResponse,
    KiwoomMarketEventSaveRequest,
    KiwoomMarketEventSaveResponse,
    DailyThemeFlowSummaryResponse,
    DailyThemeFlowStocksResponse,
    DailyThemeRanksUpdateRequest,
    DailyThemeRanksUpdateResponse,
    MonthlyThemeFlowCalendarResponse,
    MonthlyThemeFlowTrendResponse,
)
from backend.app.services.external_kiwoom_service import ExternalKiwoomService

router = APIRouter()


@router.post("/external/kiwoom/conditions/sync", response_model=KiwoomConditionSyncResponse)
def sync_kiwoom_conditions(payload: KiwoomConditionSyncRequest, db: Session = Depends(get_db)) -> KiwoomConditionSyncResponse:
    return ExternalKiwoomService(db).sync_conditions(payload)


@router.post("/external/kiwoom/conditions/refresh", response_model=KiwoomConditionRefreshResponse)
def refresh_kiwoom_conditions(db: Session = Depends(get_db)) -> KiwoomConditionRefreshResponse:
    return ExternalKiwoomService(db).refresh_conditions_from_kiwoom(source="kiwoom_rest")


@router.get("/external/kiwoom/conditions", response_model=KiwoomConditionListResponse)
def list_kiwoom_conditions(source: str = Query(default="kiwoom_rest"), db: Session = Depends(get_db)) -> KiwoomConditionListResponse:
    return ExternalKiwoomService(db).list_conditions(source=source)


@router.post("/external/kiwoom/conditions/{condition_seq}/results", response_model=KiwoomConditionResultSaveResponse)
def save_kiwoom_condition_results(
    condition_seq: str,
    payload: KiwoomConditionResultSaveRequest,
    db: Session = Depends(get_db),
) -> KiwoomConditionResultSaveResponse:
    return ExternalKiwoomService(db).save_condition_results(condition_seq=condition_seq, payload=payload)


@router.get("/external/kiwoom/conditions/{condition_seq}/results", response_model=KiwoomConditionResultListResponse)
def list_kiwoom_condition_results(
    condition_seq: str,
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> KiwoomConditionResultListResponse:
    return ExternalKiwoomService(db).list_condition_results(condition_seq=condition_seq, limit=limit)


@router.post("/external/kiwoom/conditions/{condition_seq}/preview", response_model=KiwoomConditionPreviewResponse)
def preview_kiwoom_condition_results(
    condition_seq: str,
    payload: KiwoomConditionPreviewRequest,
    db: Session = Depends(get_db),
) -> KiwoomConditionPreviewResponse:
    return ExternalKiwoomService(db).preview_condition_results(condition_seq=condition_seq, payload=payload)


@router.post("/external/kiwoom/market-events", response_model=KiwoomMarketEventSaveResponse)
def save_kiwoom_market_events(
    payload: KiwoomMarketEventSaveRequest,
    db: Session = Depends(get_db),
) -> KiwoomMarketEventSaveResponse:
    return ExternalKiwoomService(db).save_market_events(payload=payload)


@router.get("/external/kiwoom/market-events", response_model=KiwoomMarketEventListResponse)
def list_kiwoom_market_events(
    trade_date: str = Query(..., description="YYYY-MM-DD"),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> KiwoomMarketEventListResponse:
    return ExternalKiwoomService(db).list_market_events(trade_date=trade_date, limit=limit)


@router.patch("/external/kiwoom/market-events/{event_id}", response_model=KiwoomMarketEventPatchResponse)
def patch_kiwoom_market_event(
    event_id: int,
    payload: KiwoomMarketEventPatchRequest,
    db: Session = Depends(get_db),
) -> KiwoomMarketEventPatchResponse:
    return ExternalKiwoomService(db).patch_market_event(event_id=event_id, payload=payload)


@router.delete("/external/kiwoom/market-events/{event_id}", response_model=KiwoomMarketEventDeleteResponse)
def delete_kiwoom_market_event(
    event_id: int,
    db: Session = Depends(get_db),
) -> KiwoomMarketEventDeleteResponse:
    return ExternalKiwoomService(db).delete_market_event(event_id=event_id)


@router.get("/external/kiwoom/market-events/{event_id}/themes", response_model=KiwoomMarketEventThemeLinkListResponse)
def list_kiwoom_market_event_themes(
    event_id: int,
    db: Session = Depends(get_db),
) -> KiwoomMarketEventThemeLinkListResponse:
    return ExternalKiwoomService(db).list_market_event_themes(event_id=event_id)


@router.post("/external/kiwoom/market-events/{event_id}/themes", response_model=KiwoomMarketEventThemeLinkAddResponse)
def add_kiwoom_market_event_theme(
    event_id: int,
    payload: KiwoomMarketEventThemeLinkAddRequest,
    db: Session = Depends(get_db),
) -> KiwoomMarketEventThemeLinkAddResponse:
    return ExternalKiwoomService(db).add_market_event_theme(event_id=event_id, payload=payload)


@router.delete("/external/kiwoom/market-events/{event_id}/themes/{link_id}", response_model=KiwoomMarketEventThemeLinkDeleteResponse)
def remove_kiwoom_market_event_theme(
    event_id: int,
    link_id: int,
    db: Session = Depends(get_db),
) -> KiwoomMarketEventThemeLinkDeleteResponse:
    return ExternalKiwoomService(db).remove_market_event_theme(event_id=event_id, link_id=link_id)


@router.get("/external/kiwoom/theme-flow/daily", response_model=DailyThemeFlowSummaryResponse)
def get_daily_theme_flow(
    trade_date: str = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
) -> DailyThemeFlowSummaryResponse:
    return ExternalKiwoomService(db).get_daily_theme_flow(trade_date=trade_date)


@router.put("/external/kiwoom/theme-flow/daily/ranks", response_model=DailyThemeRanksUpdateResponse)
def update_daily_theme_flow_ranks(
    payload: DailyThemeRanksUpdateRequest,
    db: Session = Depends(get_db),
) -> DailyThemeRanksUpdateResponse:
    return ExternalKiwoomService(db).update_daily_theme_flow_ranks(payload=payload)


@router.get("/external/kiwoom/theme-flow/daily/{market_theme_id}/stocks", response_model=DailyThemeFlowStocksResponse)
def get_daily_theme_flow_stocks(
    market_theme_id: int,
    trade_date: str = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
) -> DailyThemeFlowStocksResponse:
    return ExternalKiwoomService(db).get_daily_theme_flow_stocks(trade_date=trade_date, market_theme_id=market_theme_id)


@router.get("/external/kiwoom/theme-flow/monthly/calendar", response_model=MonthlyThemeFlowCalendarResponse)
def get_monthly_theme_flow_calendar(
    month: str = Query(..., description="YYYY-MM"),
    db: Session = Depends(get_db),
) -> MonthlyThemeFlowCalendarResponse:
    return ExternalKiwoomService(db).get_monthly_theme_flow_calendar(month=month)


@router.get("/external/kiwoom/theme-flow/monthly/trend", response_model=MonthlyThemeFlowTrendResponse)
def get_monthly_theme_flow_trend(
    month: str = Query(..., description="YYYY-MM"),
    db: Session = Depends(get_db),
) -> MonthlyThemeFlowTrendResponse:
    return ExternalKiwoomService(db).get_monthly_theme_flow_trend(month=month)
