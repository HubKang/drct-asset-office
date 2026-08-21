from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.us_stock_schema import (
    UsExchange,
    UsStockBulkCreateResponse,
    UsStockBulkPreviewResponse,
    UsStockBulkRequest,
    UsStockCreate,
    UsStockDeleteImpactResponse,
    UsStockDeleteResponse,
    UsStockListResponse,
    UsPriceCollectionRequest,
    UsPriceCollectionResponse,
    UsStockPriceListResponse,
    UsStockResponse,
    UsStockSummaryResponse,
    UsStockType,
    UsHistoricalPriceStatus,
    UsStockUpdate,
)
from backend.app.schemas.us_market_theme_schema import UsStockChartResponse
from backend.app.services.us_stock_service import UsStockService
from backend.app.services.us_market_data_service import UsMarketDataService

router = APIRouter(prefix="/us-stocks", tags=["us-stocks"])


@router.get("", response_model=UsStockListResponse)
def list_us_stocks(keyword: str | None = None, exchange: UsExchange | None = None, stock_type: UsStockType | None = None, is_active: int | None = Query(default=None, ge=0, le=1), price_status: UsHistoricalPriceStatus | None = None, page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db)) -> UsStockListResponse:
    return UsStockService(db).list_stocks(keyword=keyword, exchange=exchange, stock_type=stock_type, is_active=is_active, price_status=price_status, page=page, page_size=page_size)


@router.get("/summary", response_model=UsStockSummaryResponse)
def get_us_stock_summary(db: Session = Depends(get_db)) -> UsStockSummaryResponse:
    return UsStockService(db).summary()


@router.post("/prices/collect", response_model=UsPriceCollectionResponse)
def collect_us_stock_prices(payload: UsPriceCollectionRequest, db: Session = Depends(get_db)) -> UsPriceCollectionResponse:
    return UsMarketDataService(db).collect_prices(payload)


@router.get("/{stock_id}/prices", response_model=UsStockPriceListResponse)
def list_us_stock_prices(stock_id: int, start_date: str | None = None, end_date: str | None = None, db: Session = Depends(get_db)) -> UsStockPriceListResponse:
    return UsMarketDataService(db).list_prices(stock_id, start_date=start_date, end_date=end_date)


@router.get("/{stock_id}/naver-charts", response_model=UsStockChartResponse)
def get_us_stock_naver_charts(stock_id: int, response: Response, db: Session = Depends(get_db)) -> UsStockChartResponse:
    response.headers["Cache-Control"] = "no-store"
    return UsStockService(db).get_naver_charts(stock_id)


@router.get("/{stock_id}/delete-impact", response_model=UsStockDeleteImpactResponse)
def get_us_stock_delete_impact(stock_id: int, db: Session = Depends(get_db)) -> UsStockDeleteImpactResponse:
    return UsStockService(db).get_delete_impact(stock_id)


@router.post("", response_model=UsStockResponse, status_code=status.HTTP_201_CREATED)
def create_us_stock(payload: UsStockCreate, db: Session = Depends(get_db)) -> UsStockResponse:
    return UsStockService(db).create_stock(payload)


@router.post("/bulk/preview", response_model=UsStockBulkPreviewResponse)
def preview_us_stock_bulk(payload: UsStockBulkRequest, db: Session = Depends(get_db)) -> UsStockBulkPreviewResponse:
    return UsStockService(db).preview_bulk(payload)


@router.post("/bulk", response_model=UsStockBulkCreateResponse, status_code=status.HTTP_201_CREATED)
def create_us_stock_bulk(payload: UsStockBulkRequest, db: Session = Depends(get_db)) -> UsStockBulkCreateResponse:
    return UsStockService(db).create_bulk(payload)


@router.patch("/{stock_id}", response_model=UsStockResponse)
def update_us_stock(stock_id: int, payload: UsStockUpdate, db: Session = Depends(get_db)) -> UsStockResponse:
    return UsStockService(db).update_stock(stock_id, payload)


@router.delete("/{stock_id}", response_model=UsStockDeleteResponse)
def delete_us_stock(stock_id: int, confirm_symbol: str = Query(min_length=1, max_length=20), db: Session = Depends(get_db)) -> UsStockDeleteResponse:
    return UsStockService(db).delete_stock(stock_id, confirm_symbol=confirm_symbol)
