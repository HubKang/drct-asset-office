from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.stock_investor_flow_schema import (
    InvestorFlowChartResponse,
    InvestorFlowCollectRequest,
    InvestorFlowCollectResponse,
)
from backend.app.services.stock_investor_flow_service import StockInvestorFlowService

router = APIRouter()


@router.post("/watchlist/collect-investor-flows", response_model=InvestorFlowCollectResponse)
def collect_investor_flows(
    payload: InvestorFlowCollectRequest,
    db: Session = Depends(get_db),
) -> InvestorFlowCollectResponse:
    return StockInvestorFlowService(db).collect(payload)


@router.get("/watchlist/sije-sucha-jae/{watchlist_id}/investor-flows", response_model=InvestorFlowChartResponse)
def get_sije_sucha_jae_investor_flows(
    watchlist_id: int,
    days: int = Query(default=30, ge=1, le=120),
    db: Session = Depends(get_db),
) -> InvestorFlowChartResponse:
    return StockInvestorFlowService(db).chart_for_watchlist(watchlist_id=watchlist_id, days=days)
