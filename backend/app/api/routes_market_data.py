from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.market_data_schema import (
    MarketDataCollectRequest,
    MarketDataCollectResponse,
    MarketDataCollectionRun,
    MarketDataCollectionRunItemListResponse,
    MarketDataCollectionRunListResponse,
)
from backend.app.services.market_data_collection_service import MarketDataCollectionService

router = APIRouter()


@router.post("/market-data/collect", response_model=MarketDataCollectResponse)
def collect_market_data(payload: MarketDataCollectRequest, db: Session = Depends(get_db)) -> MarketDataCollectResponse:
    return MarketDataCollectionService(db).collect(payload)


@router.get("/market-data/collection-runs", response_model=MarketDataCollectionRunListResponse)
def list_market_data_collection_runs(
    limit: int = Query(default=30, ge=1, le=200),
    db: Session = Depends(get_db),
) -> MarketDataCollectionRunListResponse:
    return MarketDataCollectionService(db).list_runs(limit=limit)


@router.get("/market-data/collection-runs/{run_id}", response_model=MarketDataCollectionRun)
def get_market_data_collection_run(run_id: int, db: Session = Depends(get_db)) -> MarketDataCollectionRun:
    return MarketDataCollectionService(db).get_run(run_id)


@router.get("/market-data/collection-runs/{run_id}/items", response_model=MarketDataCollectionRunItemListResponse)
def list_market_data_collection_run_items(run_id: int, db: Session = Depends(get_db)) -> MarketDataCollectionRunItemListResponse:
    return MarketDataCollectionService(db).list_run_items(run_id)
