from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.stock_price_schema import (
    SelectedStockPriceCollectRequest,
    StockDailyPriceResponse,
    StockPriceCollectResult,
    StockPriceUpdateRequest,
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


@router.post("/stock-prices/update/selected", response_model=StockPriceCollectResult)
def update_selected_prices(payload: StockPriceUpdateRequest, db: Session = Depends(get_db)) -> StockPriceCollectResult:
    return StockPriceService(db).update_selected_recent(
        stock_ids=payload.stock_ids,
        source=payload.source,
    )


@router.get("/stock-prices/{stock_id}/daily", response_model=list[StockDailyPriceResponse])
def list_stock_daily_prices(
    stock_id: int,
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[StockDailyPriceResponse]:
    return StockPriceService(db).list_daily(
        stock_id=stock_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )
