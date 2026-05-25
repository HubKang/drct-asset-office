from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.kiwoom_schema import KiwoomPocDailyPriceRequest, KiwoomPocDailyPriceResponse
from backend.app.services.kiwoom_market_data_poc_service import KiwoomMarketDataPocService

router = APIRouter()


@router.get("/kiwoom/poc/daily-price", response_model=KiwoomPocDailyPriceResponse)
def get_kiwoom_daily_price_poc(
    ticker: str = Query(..., description="6자리 종목코드, 예: 097230"),
    mode: str = Query(default="recent", description="recent | backfill"),
    years: int = Query(default=2, ge=1, le=5),
    start_date: str | None = Query(default=None, description="YYYY-MM-DD 또는 YYYYMMDD"),
    end_date: str | None = Query(default=None, description="YYYY-MM-DD 또는 YYYYMMDD"),
    max_pages: int | None = Query(default=None, ge=1, le=200),
    repeat_calls: int = Query(default=1, ge=1, le=20),
    api_id: str | None = Query(default=None),
    endpoint: str | None = Query(default=None),
    save: bool = Query(default=False),
    calculate_technical: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> KiwoomPocDailyPriceResponse:
    return KiwoomMarketDataPocService(db).run_daily_price_poc(
        ticker=ticker,
        mode=mode,
        years=years,
        start_date=start_date,
        end_date=end_date,
        max_pages=max_pages,
        repeat_calls=repeat_calls,
        api_id=api_id,
        endpoint=endpoint,
        save=save,
        calculate_technical=calculate_technical,
    )


@router.post("/kiwoom/poc/daily-price", response_model=KiwoomPocDailyPriceResponse)
def post_kiwoom_daily_price_poc(
    payload: KiwoomPocDailyPriceRequest,
    db: Session = Depends(get_db),
) -> KiwoomPocDailyPriceResponse:
    return KiwoomMarketDataPocService(db).run_daily_price_poc(
        ticker=payload.ticker,
        mode=payload.mode,
        years=payload.years,
        start_date=payload.start_date,
        end_date=payload.end_date,
        max_pages=payload.max_pages,
        repeat_calls=payload.repeat_calls,
        api_id=payload.api_id,
        endpoint=payload.endpoint,
        save=payload.save,
        calculate_technical=payload.calculate_technical,
    )
