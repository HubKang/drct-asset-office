from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.schemas.stock_financial_schema import StockFinancialCollectRequest, StockFinancialCollectResponse, StockFinancialDataResponse
from backend.app.services.stock_financial_service import StockFinancialService

router=APIRouter()

@router.post("/stock-financials/collect/selected", response_model=StockFinancialCollectResponse)
def collect_selected(payload: StockFinancialCollectRequest, db: Session=Depends(get_db)) -> StockFinancialCollectResponse:
    return StockFinancialService(db).collect_selected(payload.stock_ids)

@router.get("/stock-financials/{stock_id}", response_model=StockFinancialDataResponse)
def get_data(stock_id: int, db: Session=Depends(get_db)) -> StockFinancialDataResponse:
    return StockFinancialService(db).get_data(stock_id)
