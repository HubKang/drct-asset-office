from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.stock_market_metric_schema import (
    MarketMetricsDailyCollectRequest,
    MarketMetricsDailyCollectResponse,
    StockMarketMetricLatestResponse,
    StockMarketMetricSummaryResponse,
)
from backend.app.services.stock_market_metric_service import StockMarketMetricService

router = APIRouter(prefix="/market-metrics", tags=["market-metrics"])


@router.post("/collect/daily", response_model=MarketMetricsDailyCollectResponse)
def collect_market_metrics_daily(
    payload: MarketMetricsDailyCollectRequest,
    db: Session = Depends(get_db),
) -> MarketMetricsDailyCollectResponse:
    return StockMarketMetricService(db).collect_daily(trade_date=payload.trade_date, source=payload.source)


@router.get("/{stock_id}/latest", response_model=StockMarketMetricLatestResponse)
def get_latest_market_metrics(
    stock_id: int,
    source: str = "marcap",
    db: Session = Depends(get_db),
) -> StockMarketMetricLatestResponse:
    return StockMarketMetricService(db).get_latest(stock_id=stock_id, source=source)


@router.get("/{stock_id}/summary", response_model=StockMarketMetricSummaryResponse)
def get_market_metrics_summary(
    stock_id: int,
    source: str = "marcap",
    db: Session = Depends(get_db),
) -> StockMarketMetricSummaryResponse:
    return StockMarketMetricService(db).get_summary(stock_id=stock_id, source=source)
