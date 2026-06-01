from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.stock_price_schema import (
    SelectedStockPriceCollectRequest,
    StockPriceCollectResult,
    StockDailyPriceListResponse,
    StockPriceFactSummaryResponse,
    StockPriceSummaryResponse,
    TechnicalIndicatorBatchCalculateRequest,
    TechnicalIndicatorBatchCalculateResponse,
    TechnicalIndicatorCalculateResponse,
)
from backend.app.services.stock_price_service import StockPriceService

router = APIRouter()


@router.post("/stock-prices/collect/selected", response_model=StockPriceCollectResult)
def collect_selected_prices(payload: SelectedStockPriceCollectRequest, db: Session = Depends(get_db)) -> StockPriceCollectResult:
    return StockPriceService(db).collect_selected_backfill(
        stock_ids=payload.stock_ids,
        period_years=payload.period_years,
        source=payload.source,
    )


@router.get("/stock-prices/summary", response_model=StockPriceSummaryResponse)
def list_stock_price_summary(
    keyword: str | None = Query(default=None),
    market: str | None = Query(default=None),
    source: str | None = Query(default=None),
    scope: str | None = Query(default="watchlist"),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> StockPriceSummaryResponse:
    return StockPriceService(db).list_summary(
        keyword=keyword,
        market=market,
        source=source,
        scope=scope,
        limit=limit,
        offset=offset,
    )


@router.post("/technical-indicators/calculate/stock/{stock_id}", response_model=TechnicalIndicatorCalculateResponse)
def calculate_technical_indicators_for_stock(stock_id: int, db: Session = Depends(get_db)) -> TechnicalIndicatorCalculateResponse:
    return StockPriceService(db).calculate_and_save_technical_indicators(stock_id=stock_id)


@router.post("/technical-indicators/calculate/selected", response_model=TechnicalIndicatorBatchCalculateResponse)
def calculate_technical_indicators_for_selected(
    payload: TechnicalIndicatorBatchCalculateRequest,
    db: Session = Depends(get_db),
) -> TechnicalIndicatorBatchCalculateResponse:
    return StockPriceService(db).calculate_and_save_technical_indicators_for_selected(stock_ids=payload.stock_ids)


@router.get("/stock-prices/{stock_id}/summary", response_model=StockPriceFactSummaryResponse)
def get_stock_price_summary(
    stock_id: int,
    source: str = Query(default="kiwoom_rest"),
    db: Session = Depends(get_db),
) -> StockPriceFactSummaryResponse:
    return StockPriceService(db).get_summary(stock_id=stock_id, source=source)


@router.get("/stock-prices/{stock_id}/daily", response_model=StockDailyPriceListResponse)
def list_stock_daily_prices(
    stock_id: int,
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    source: str | None = Query(default="kiwoom_rest"),
    limit: int = Query(default=100, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> StockDailyPriceListResponse:
    return StockPriceService(db).list_daily(
        stock_id=stock_id,
        start_date=start_date,
        end_date=end_date,
        source=source,
        limit=limit,
        offset=offset,
    )
