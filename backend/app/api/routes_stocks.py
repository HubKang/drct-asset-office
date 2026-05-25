from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.stock_schema import (
    StockCodeNormalizeRequest,
    StockCodeNormalizeResponse,
    StockCreate,
    StockResponse,
    StockUpdate,
)
from backend.app.schemas.stock_sync_schema import StockSyncRequest, StockSyncResponse
from backend.app.services.stock_service import StockService
from backend.app.services.stock_sync_service import StockSyncService

router = APIRouter()


@router.post("/stocks", response_model=StockResponse, status_code=status.HTTP_201_CREATED)
def create_stock(payload: StockCreate, db: Session = Depends(get_db)) -> StockResponse:
    return StockService(db).create_stock(payload)


@router.get("/stocks", response_model=list[StockResponse])
def list_stocks(
    keyword: str | None = None,
    is_active: int | None = Query(default=None),
    market: str | None = Query(default=None),
    security_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[StockResponse]:
    return StockService(db).list_stocks(
        keyword=keyword,
        is_active=is_active,
        market=market,
        security_type=security_type,
        limit=limit,
        offset=offset,
    )


@router.get("/stocks/{stock_id}", response_model=StockResponse)
def get_stock(stock_id: int, db: Session = Depends(get_db)) -> StockResponse:
    return StockService(db).get_stock(stock_id)


@router.put("/stocks/{stock_id}", response_model=StockResponse)
def update_stock(stock_id: int, payload: StockUpdate, db: Session = Depends(get_db)) -> StockResponse:
    return StockService(db).update_stock(stock_id, payload)


@router.delete("/stocks/{stock_id}", response_model=StockResponse)
def delete_stock(stock_id: int, db: Session = Depends(get_db)) -> StockResponse:
    return StockService(db).deactivate_stock(stock_id)


@router.post("/stocks/sync", response_model=StockSyncResponse)
def sync_stocks(payload: StockSyncRequest, db: Session = Depends(get_db)) -> StockSyncResponse:
    return StockSyncService(db).sync_stocks(
        markets=payload.markets,
        dry_run=payload.dry_run,
        deactivate_missing=payload.deactivate_missing,
        include_security_types=payload.include_security_types,
    )


@router.post("/stocks/normalize-codes", response_model=StockCodeNormalizeResponse)
def normalize_stock_codes(payload: StockCodeNormalizeRequest, db: Session = Depends(get_db)) -> StockCodeNormalizeResponse:
    return StockService(db).normalize_stock_codes(payload)
