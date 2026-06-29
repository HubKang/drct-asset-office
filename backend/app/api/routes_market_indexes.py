from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.market_index_schema import (
    MarketIndexCollectRequest,
    MarketIndexCollectResponse,
    MarketIndexCompareResponse,
    MarketIndexDailyPriceListResponse,
    MarketIndexListResponse,
)
from backend.app.services.market_index_service import MarketIndexService

router = APIRouter()


@router.get("/market-indexes", response_model=MarketIndexListResponse)
def list_market_indexes(
    active_only: bool = Query(default=True),
    category: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> MarketIndexListResponse:
    return MarketIndexService(db).list_indexes(active_only=active_only, category=category)


@router.post("/market-indexes/collect", response_model=MarketIndexCollectResponse)
def collect_market_indexes(
    payload: MarketIndexCollectRequest,
    db: Session = Depends(get_db),
) -> MarketIndexCollectResponse:
    return MarketIndexService(db).collect(
        index_codes=payload.index_codes,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )


@router.get("/market-indexes/compare", response_model=MarketIndexCompareResponse)
def compare_market_indexes(
    index_codes: str = Query(default="KOSPI,KOSDAQ"),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    normalize: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> MarketIndexCompareResponse:
    return MarketIndexService(db).compare_indexes(
        index_codes=index_codes.split(","),
        start_date=start_date,
        end_date=end_date,
        normalize=normalize,
    )


@router.get("/market-indexes/{index_code}/daily-prices", response_model=MarketIndexDailyPriceListResponse)
def list_market_index_daily_prices(
    index_code: str,
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> MarketIndexDailyPriceListResponse:
    return MarketIndexService(db).get_daily_prices(index_code=index_code, start_date=start_date, end_date=end_date)
