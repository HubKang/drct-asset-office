from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.market_theme_schema import (
    MarketThemeCreateRequest,
    MarketThemeResponse,
    MarketThemeUpdateRequest,
)
from backend.app.schemas.market_theme_stock_schema import (
    MarketThemeByStockResponse,
    MarketThemeStockMemoResponse,
    MarketThemeStockCreateRequest,
    MarketThemeStockResponse,
    MarketThemeStockMemoUpdateRequest,
    MarketThemeStockSupplySummaryResponse,
    MarketThemeStockUpdateRequest,
)
from backend.app.services.market_theme_service import MarketThemeService
from backend.app.services.market_theme_stock_service import MarketThemeStockService
from backend.app.services.market_theme_flow_trend_service import invalidate_market_theme_flow_trend_cache

router = APIRouter()


@router.get("/market-themes", response_model=list[MarketThemeResponse])
def list_market_themes(
    is_active: int | None = Query(default=None),
    theme_type: str | None = Query(default=None),
    theme_level: str | None = Query(default=None),
    parent_theme_id: int | None = Query(default=None),
    is_supply_theme: int | None = Query(default=None),
    keyword: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[MarketThemeResponse]:
    return MarketThemeService(db).list_themes(
        is_active=is_active,
        theme_type=theme_type,
        theme_level=theme_level,
        parent_theme_id=parent_theme_id,
        is_supply_theme=is_supply_theme,
        keyword=keyword,
        limit=limit,
        offset=offset,
    )


@router.get("/market-themes/{theme_id}", response_model=MarketThemeResponse)
def get_market_theme(theme_id: int, db: Session = Depends(get_db)) -> MarketThemeResponse:
    return MarketThemeService(db).get_theme(theme_id)


@router.post("/market-themes", response_model=MarketThemeResponse)
def create_market_theme(payload: MarketThemeCreateRequest, db: Session = Depends(get_db)) -> MarketThemeResponse:
    result = MarketThemeService(db).create_theme(payload)
    invalidate_market_theme_flow_trend_cache()
    return result


@router.put("/market-themes/{theme_id}", response_model=MarketThemeResponse)
def update_market_theme(theme_id: int, payload: MarketThemeUpdateRequest, db: Session = Depends(get_db)) -> MarketThemeResponse:
    result = MarketThemeService(db).update_theme(theme_id, payload)
    invalidate_market_theme_flow_trend_cache()
    return result


@router.patch("/market-themes/{theme_id}/deactivate", response_model=MarketThemeResponse)
def deactivate_market_theme(theme_id: int, db: Session = Depends(get_db)) -> MarketThemeResponse:
    result = MarketThemeService(db).deactivate_theme(theme_id)
    invalidate_market_theme_flow_trend_cache()
    return result


@router.get("/market-themes/{theme_id}/stocks", response_model=list[MarketThemeStockResponse])
def list_market_theme_stocks(theme_id: int, db: Session = Depends(get_db)) -> list[MarketThemeStockResponse]:
    return MarketThemeStockService(db).list_theme_stocks(theme_id)


@router.get(
    "/market-themes/{theme_id}/stocks/{stock_id}/supply-summary",
    response_model=MarketThemeStockSupplySummaryResponse,
)
def get_market_theme_stock_supply_summary(
    theme_id: int,
    stock_id: int,
    db: Session = Depends(get_db),
) -> MarketThemeStockSupplySummaryResponse:
    return MarketThemeStockService(db).get_supply_summary(theme_id, stock_id)


@router.post("/market-themes/{theme_id}/stocks", response_model=MarketThemeStockResponse)
def create_market_theme_stock(
    theme_id: int,
    payload: MarketThemeStockCreateRequest,
    db: Session = Depends(get_db),
) -> MarketThemeStockResponse:
    result = MarketThemeStockService(db).create_theme_stock(theme_id, payload)
    invalidate_market_theme_flow_trend_cache()
    return result


@router.patch("/market-themes/{theme_id}/stocks/{stock_id}/memo", response_model=MarketThemeStockResponse)
def update_market_theme_stock_memo(
    theme_id: int,
    stock_id: int,
    payload: MarketThemeStockMemoUpdateRequest,
    db: Session = Depends(get_db),
) -> MarketThemeStockResponse:
    return MarketThemeStockService(db).update_theme_stock_memo(theme_id, stock_id, payload)


@router.patch("/market-theme-stocks/{mapping_id}", response_model=MarketThemeStockResponse)
def update_market_theme_stock(
    mapping_id: int,
    payload: MarketThemeStockUpdateRequest,
    db: Session = Depends(get_db),
) -> MarketThemeStockResponse:
    result = MarketThemeStockService(db).update_theme_stock(mapping_id, payload)
    invalidate_market_theme_flow_trend_cache()
    return result


@router.patch("/market-theme-stocks/{mapping_id}/deactivate", response_model=MarketThemeStockResponse)
def deactivate_market_theme_stock(mapping_id: int, db: Session = Depends(get_db)) -> MarketThemeStockResponse:
    result = MarketThemeStockService(db).deactivate_theme_stock(mapping_id)
    invalidate_market_theme_flow_trend_cache()
    return result


@router.get("/market-themes/by-stock/{stock_code}", response_model=MarketThemeByStockResponse)
def list_market_themes_by_stock(stock_code: str, db: Session = Depends(get_db)) -> MarketThemeByStockResponse:
    return MarketThemeStockService(db).list_themes_by_stock_code(stock_code)


@router.get("/market-themes/stocks/{stock_code}/memos", response_model=MarketThemeStockMemoResponse)
def list_market_theme_stock_memos(stock_code: str, db: Session = Depends(get_db)) -> MarketThemeStockMemoResponse:
    return MarketThemeStockService(db).list_stock_memos(stock_code)
