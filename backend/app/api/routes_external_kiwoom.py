from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Query
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
    MarketThemeLatestReturnResponse,
    MarketThemeMonthlyReturnResponse,
    MarketThemePriceFlowJobStartResponse,
    MarketThemePriceFlowJobStatusResponse,
    MarketThemePriceFlowRefreshResponse,
    MarketThemeReturnRefreshRequest,
    MarketThemeReturnRefreshResponse,
    MonthlyThemeFlowCalendarResponse,
    MonthlyThemeFlowTrendResponse,
    MonthlyThemeCellDetailResponse,
    SupplyTopStockReturnTrendResponse,
    SupplyTopStockPriceCollectRequest,
    SupplyTopStockPriceCollectResponse,
)
from backend.app.schemas.market_theme_stock_schema import MarketThemeFlowChartResponse, MarketThemeFlowTrendResponse, MarketThemePriceFlowChartResponse
from backend.app.services.external_kiwoom_service import ExternalKiwoomService
from backend.app.services.market_theme_price_flow_chart_service import MarketThemePriceFlowChartService
from backend.app.services.market_theme_flow_analysis_service import MarketThemeFlowAnalysisService
from backend.app.services.market_theme_flow_trend_service import MarketThemeFlowTrendService, invalidate_market_theme_flow_trend_cache
from backend.app.services.monthly_theme_cell_detail_service import MonthlyThemeCellDetailService
from backend.app.services.market_theme_price_flow_collection_service import (
    MarketThemePriceFlowCollectionService,
    MarketThemePriceFlowJobManager,
)

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



@router.post("/external/kiwoom/market-themes/returns/refresh", response_model=MarketThemeReturnRefreshResponse)
def refresh_market_theme_returns(
    payload: MarketThemeReturnRefreshRequest | None = None,
    db: Session = Depends(get_db),
) -> MarketThemeReturnRefreshResponse:
    result = ExternalKiwoomService(db).refresh_market_theme_returns(payload or MarketThemeReturnRefreshRequest())
    invalidate_market_theme_flow_trend_cache()
    return result


@router.post(
    "/external/kiwoom/market-themes/returns-and-flows/refresh",
    response_model=MarketThemePriceFlowRefreshResponse,
)
def refresh_market_theme_returns_and_flows(
    payload: MarketThemeReturnRefreshRequest | None = None,
    db: Session = Depends(get_db),
) -> MarketThemePriceFlowRefreshResponse:
    result = MarketThemePriceFlowCollectionService(db).refresh(payload or MarketThemeReturnRefreshRequest())
    invalidate_market_theme_flow_trend_cache()
    return result


@router.post(
    "/external/kiwoom/market-themes/returns-and-flows/jobs",
    response_model=MarketThemePriceFlowJobStartResponse,
)
def start_market_theme_returns_and_flows_job(
    background_tasks: BackgroundTasks,
    payload: MarketThemeReturnRefreshRequest | None = None,
) -> MarketThemePriceFlowJobStartResponse:
    job_id = MarketThemePriceFlowJobManager.start(payload or MarketThemeReturnRefreshRequest())
    background_tasks.add_task(MarketThemePriceFlowJobManager.run, job_id)
    job = MarketThemePriceFlowJobManager.get(job_id)
    return MarketThemePriceFlowJobStartResponse(
        job_id=job_id,
        status="PENDING",
        message=str(job["message"]),
        requested_at=str(job["requested_at"]),
    )


@router.get(
    "/external/kiwoom/market-themes/returns-and-flows/jobs/{job_id}",
    response_model=MarketThemePriceFlowJobStatusResponse,
)
def get_market_theme_returns_and_flows_job(job_id: str) -> MarketThemePriceFlowJobStatusResponse:
    return MarketThemePriceFlowJobStatusResponse(**MarketThemePriceFlowJobManager.get(job_id))


@router.get(
    "/external/kiwoom/market-themes/stocks/{stock_id}/price-flow-chart",
    response_model=MarketThemePriceFlowChartResponse,
)
def get_market_theme_stock_price_flow_chart(
    stock_id: int,
    period: str = Query(default="3M"),
    unit: str = Query(default="QUANTITY"),
    view: str = Query(default="ACTUAL"),
    theme_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> MarketThemePriceFlowChartResponse:
    """Read saved prices and flows only; this endpoint never starts collection."""
    return MarketThemePriceFlowChartService(db).get_chart(
        stock_id,
        period=period,
        unit=unit,
        view=view,
        theme_id=theme_id,
    )


@router.get(
    "/external/kiwoom/market-themes/flow-trend",
    response_model=MarketThemeFlowTrendResponse,
)
def get_market_theme_flow_trend(
    end_date: str = Query(...),
    recent_days: int = Query(default=30, ge=1, le=60),
    actor: str = Query(default="FOREIGN"),
    metric: str = Query(default="FLOW_STRENGTH"),
    attribution: str = Query(default="FRACTIONAL"),
    theme_group_id: int | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=100),
    refresh: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> MarketThemeFlowTrendResponse:
    """Aggregate saved theme flows only. No provider collection is triggered."""
    return MarketThemeFlowTrendService(db).get_trend(
        end_date=end_date, recent_days=recent_days, actor=actor, metric=metric,
        attribution=attribution, theme_group_id=theme_group_id, search=search,
        limit=limit, refresh=refresh,
    )


@router.get(
    "/external/kiwoom/market-themes/{theme_id}/price-flow-chart",
    response_model=MarketThemeFlowChartResponse,
)
def get_market_theme_price_flow_chart(
    theme_id: int,
    period: str = Query(default="3M"),
    focus_date: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> MarketThemeFlowChartResponse:
    return MarketThemeFlowAnalysisService(db).get_chart(
        theme_id, period=period, focus_date=focus_date
    )


@router.get("/external/kiwoom/market-themes/{theme_id}/returns/latest", response_model=MarketThemeLatestReturnResponse)
def get_market_theme_latest_return(theme_id: int, db: Session = Depends(get_db)) -> MarketThemeLatestReturnResponse:
    return ExternalKiwoomService(db).get_market_theme_latest_return(theme_id=theme_id)


@router.get("/external/kiwoom/market-themes/returns/monthly", response_model=MarketThemeMonthlyReturnResponse)
def get_market_theme_monthly_returns(
    month: str = Query(..., description="YYYY-MM"),
    active_only: bool = Query(True),
    theme_group_id: int | None = Query(None),
    keyword: str | None = Query(None),
    limit: int | None = Query(None),
    lookback_days: int = Query(0),
    db: Session = Depends(get_db),
) -> MarketThemeMonthlyReturnResponse:
    return ExternalKiwoomService(db).get_market_theme_monthly_returns(
        month=month,
        active_only=active_only,
        theme_group_id=theme_group_id,
        keyword=keyword,
        limit=limit,
        lookback_days=lookback_days,
    )




@router.get("/external/kiwoom/market-themes/returns/range", response_model=MarketThemeMonthlyReturnResponse)
def get_market_theme_range_returns(
    end_date: str = Query(..., description="YYYY-MM-DD"),
    days: int = Query(30),
    active_only: bool = Query(True),
    theme_group_id: int | None = Query(None),
    keyword: str | None = Query(None),
    limit: int | None = Query(None),
    sort_by: str = Query("CURRENT_STRENGTH"),
    db: Session = Depends(get_db),
) -> MarketThemeMonthlyReturnResponse:
    return ExternalKiwoomService(db).get_market_theme_range_returns(
        end_date=end_date,
        days=days,
        active_only=active_only,
        theme_group_id=theme_group_id,
        keyword=keyword,
        limit=limit,
        sort_by=sort_by,
    )
@router.get("/external/kiwoom/market-themes/{theme_id}/returns/daily", response_model=MarketThemeLatestReturnResponse)
def get_market_theme_daily_return(
    theme_id: int,
    date: str = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
) -> MarketThemeLatestReturnResponse:
    return ExternalKiwoomService(db).get_market_theme_daily_return(theme_id=theme_id, return_date=date)
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


@router.get(
    "/external/kiwoom/theme-flow/monthly/themes/{theme_id}/dates/{event_date}/stocks",
    response_model=MonthlyThemeCellDetailResponse,
)
def get_monthly_theme_cell_detail(
    theme_id: int,
    event_date: str,
    period_from: str = Query(..., description="YYYY-MM-DD"),
    period_to: str = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
) -> MonthlyThemeCellDetailResponse:
    """Return saved event stocks and selected-date price/flow data in one read-only query flow."""
    return MonthlyThemeCellDetailService(db).get_detail(
        theme_id=theme_id,
        event_date=event_date,
        period_from=period_from,
        period_to=period_to,
    )

@router.get("/external/kiwoom/theme-flow/monthly/calendar", response_model=MonthlyThemeFlowCalendarResponse)
def get_monthly_theme_flow_calendar(
    month: str = Query(..., description="YYYY-MM"),
    db: Session = Depends(get_db),
) -> MonthlyThemeFlowCalendarResponse:
    return ExternalKiwoomService(db).get_monthly_theme_flow_calendar(month=month)


@router.get(
    "/external/kiwoom/theme-flow/monthly/top-stock-return-trend",
    response_model=SupplyTopStockReturnTrendResponse,
)
def get_supply_top_stock_return_trend(
    period_start_date: str = Query(..., description="YYYY-MM-DD"),
    period_end_date: str = Query(..., description="YYYY-MM-DD"),
    limit: int = Query(default=20, ge=1, le=20),
    db: Session = Depends(get_db),
) -> SupplyTopStockReturnTrendResponse:
    return ExternalKiwoomService(db).get_supply_top_stock_return_trend(
        period_start_date=period_start_date,
        period_end_date=period_end_date,
        limit=limit,
    )

@router.post(
    "/external/kiwoom/theme-flow/monthly/top-stock-return-trend/collect-missing-prices",
    response_model=SupplyTopStockPriceCollectResponse,
    include_in_schema=False,
)
@router.post(
    "/external/kiwoom/theme-flow/monthly/top-stock-return-trend/refresh-prices",
    response_model=SupplyTopStockPriceCollectResponse,
)
def refresh_supply_top_stock_prices(
    payload: SupplyTopStockPriceCollectRequest,
    db: Session = Depends(get_db),
) -> SupplyTopStockPriceCollectResponse:
    return ExternalKiwoomService(db).refresh_supply_top_stock_prices(payload)

@router.get("/external/kiwoom/theme-flow/monthly/trend", response_model=MonthlyThemeFlowTrendResponse)
def get_monthly_theme_flow_trend(
    month: str = Query(..., description="YYYY-MM"),
    view_mode: str = Query(default="THEME", description="THEME_GROUP 또는 THEME"),
    theme_group_id: int | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=500),
    start_date: str | None = Query(default=None, description="YYYY-MM-DD"),
    end_date: str | None = Query(default=None, description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
) -> MonthlyThemeFlowTrendResponse:
    return ExternalKiwoomService(db).get_monthly_theme_flow_trend(
        month=month,
        view_mode=view_mode,
        theme_group_id=theme_group_id,
        limit=limit,
        start_date=start_date,
        end_date=end_date,
    )
