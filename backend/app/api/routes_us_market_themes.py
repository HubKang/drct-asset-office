from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.us_market_theme_schema import (
    UsThemeGroupInput,
    UsThemeGroupResponse,
    UsThemeGroupUpdate,
    UsThemeInput,
    UsThemeResponse,
    UsThemeStockInput,
    UsThemeStockResponse,
    UsThemeStockUpdate,
    UsThemeSummaryResponse,
    UsThemeUpdate,
    UsMarketRefreshRequest,
    UsMarketRefreshResponse,
    UsThemeReturnDetailResponse,
    UsThemeReturnListResponse,
    UsThemeTreemapResponse,
    UsThemeReturnRecalculateRequest,
    UsThemeReturnRecalculateResponse,
    UsThemeTrendResponse,
)
from backend.app.services.us_market_theme_service import UsMarketThemeService
from backend.app.services.us_market_data_service import UsMarketDataService

router = APIRouter(prefix="/us-market-themes", tags=["us-market-themes"])


@router.get("/summary", response_model=UsThemeSummaryResponse)
def get_summary(db: Session = Depends(get_db)) -> UsThemeSummaryResponse:
    return UsMarketThemeService(db).summary()


@router.post("/refresh", response_model=UsMarketRefreshResponse)
def refresh_us_market(payload: UsMarketRefreshRequest, db: Session = Depends(get_db)) -> UsMarketRefreshResponse:
    return UsMarketDataService(db).refresh(payload)


@router.post("/returns/recalculate", response_model=UsThemeReturnRecalculateResponse)
def recalculate_us_theme_returns(payload: UsThemeReturnRecalculateRequest, db: Session = Depends(get_db)) -> UsThemeReturnRecalculateResponse:
    return UsMarketDataService(db).recalculate_returns(payload)


@router.get("/returns/latest", response_model=UsThemeReturnListResponse)
def get_latest_us_theme_returns(db: Session = Depends(get_db)) -> UsThemeReturnListResponse:
    return UsMarketDataService(db).latest_returns()


@router.get("/treemap", response_model=UsThemeTreemapResponse)
def get_us_theme_treemap(db: Session = Depends(get_db)) -> UsThemeTreemapResponse:
    return UsMarketDataService(db).treemap()


@router.get("/returns/trend", response_model=UsThemeTrendResponse)
def get_us_theme_return_trend(
    period: str = Query(default="30", pattern="^(20|30|60)$"),
    end_date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    active: int | None = Query(default=1, ge=0, le=1),
    db: Session = Depends(get_db),
) -> UsThemeTrendResponse:
    return UsMarketDataService(db).trend(period=int(period), end_date=end_date, active=active)


@router.get("/themes/{theme_id}/returns/{trade_date}", response_model=UsThemeReturnDetailResponse)
def get_us_theme_return_detail(theme_id: int, trade_date: str, db: Session = Depends(get_db)) -> UsThemeReturnDetailResponse:
    return UsMarketDataService(db).detail(theme_id=theme_id, trade_date=trade_date)


@router.get("/themes/{theme_id}/detail", response_model=UsThemeReturnDetailResponse)
def get_us_theme_detail(
    theme_id: int,
    trade_date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    db: Session = Depends(get_db),
) -> UsThemeReturnDetailResponse:
    return UsMarketDataService(db).detail(theme_id=theme_id, trade_date=trade_date)


@router.get("/groups", response_model=list[UsThemeGroupResponse])
def list_groups(db: Session = Depends(get_db)) -> list[UsThemeGroupResponse]:
    return UsMarketThemeService(db).list_groups()


@router.post("/groups", response_model=UsThemeGroupResponse, status_code=status.HTTP_201_CREATED)
def create_group(payload: UsThemeGroupInput, db: Session = Depends(get_db)) -> UsThemeGroupResponse:
    return UsMarketThemeService(db).create_group(payload)


@router.patch("/groups/{group_id}", response_model=UsThemeGroupResponse)
def update_group(group_id: int, payload: UsThemeGroupUpdate, db: Session = Depends(get_db)) -> UsThemeGroupResponse:
    return UsMarketThemeService(db).update_group(group_id, payload)


@router.get("/themes", response_model=list[UsThemeResponse])
def list_themes(group_id: int | None = None, active: int | None = Query(default=None, ge=0, le=1), keyword: str | None = None, db: Session = Depends(get_db)) -> list[UsThemeResponse]:
    return UsMarketThemeService(db).list_themes(group_id=group_id, active=active, keyword=keyword)


@router.post("/themes", response_model=UsThemeResponse, status_code=status.HTTP_201_CREATED)
def create_theme(payload: UsThemeInput, db: Session = Depends(get_db)) -> UsThemeResponse:
    return UsMarketThemeService(db).create_theme(payload)


@router.patch("/themes/{theme_id}", response_model=UsThemeResponse)
def update_theme(theme_id: int, payload: UsThemeUpdate, db: Session = Depends(get_db)) -> UsThemeResponse:
    return UsMarketThemeService(db).update_theme(theme_id, payload)


@router.get("/themes/{theme_id}/stocks", response_model=list[UsThemeStockResponse])
def list_theme_stocks(theme_id: int, db: Session = Depends(get_db)) -> list[UsThemeStockResponse]:
    return UsMarketThemeService(db).list_theme_stocks(theme_id)


@router.post("/themes/{theme_id}/stocks", response_model=UsThemeStockResponse, status_code=status.HTTP_201_CREATED)
def link_theme_stock(theme_id: int, payload: UsThemeStockInput, db: Session = Depends(get_db)) -> UsThemeStockResponse:
    return UsMarketThemeService(db).link_stock(theme_id, payload)


@router.patch("/mappings/{mapping_id}", response_model=UsThemeStockResponse)
def update_mapping(mapping_id: int, payload: UsThemeStockUpdate, db: Session = Depends(get_db)) -> UsThemeStockResponse:
    return UsMarketThemeService(db).update_mapping(mapping_id, payload)


@router.delete("/mappings/{mapping_id}", response_model=UsThemeStockResponse)
def unlink_mapping(mapping_id: int, db: Session = Depends(get_db)) -> UsThemeStockResponse:
    return UsMarketThemeService(db).unlink_mapping(mapping_id)
