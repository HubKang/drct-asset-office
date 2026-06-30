from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.market_indicator_schema import (
    ExternalProviderStatusListResponse,
    MarketIndicator,
    MarketIndicatorCollectRequest,
    MarketIndicatorCollectResponse,
    MarketIndicatorListResponse,
    MarketIndicatorProviderMappingListResponse,
    MarketIndicatorValueResponse,
)
from backend.app.services.external_provider_status_service import ExternalProviderStatusService
from backend.app.services.market_indicator_service import MarketIndicatorService

router = APIRouter()


@router.get("/market-indicators-data", response_model=MarketIndicatorListResponse)
def list_market_indicators(
    category: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> MarketIndicatorListResponse:
    return MarketIndicatorService(db).list_indicators(category=category, active_only=active_only)


@router.get("/market-indicators-data/provider-mappings", response_model=MarketIndicatorProviderMappingListResponse)
def list_market_indicator_provider_mappings(db: Session = Depends(get_db)) -> MarketIndicatorProviderMappingListResponse:
    return MarketIndicatorService(db).list_provider_mappings()


@router.get("/market-indicators-data/providers/status", response_model=ExternalProviderStatusListResponse)
def list_external_provider_statuses() -> ExternalProviderStatusListResponse:
    return {"items": ExternalProviderStatusService().list_statuses()}


@router.get("/market-indicators-data/{indicator_code}", response_model=MarketIndicator)
def get_market_indicator(indicator_code: str, db: Session = Depends(get_db)) -> MarketIndicator:
    return MarketIndicatorService(db).get_indicator(indicator_code)


@router.get("/market-indicators-data/{indicator_code}/values", response_model=MarketIndicatorValueResponse)
def list_market_indicator_values(
    indicator_code: str,
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> MarketIndicatorValueResponse:
    return MarketIndicatorService(db).get_indicator_values(indicator_code, start_date=start_date, end_date=end_date)


@router.post("/market-indicators-data/collect", response_model=MarketIndicatorCollectResponse)
def collect_market_indicators(
    payload: MarketIndicatorCollectRequest,
    db: Session = Depends(get_db),
) -> MarketIndicatorCollectResponse:
    return MarketIndicatorService(db).collect_indicator(payload.indicator_codes)
