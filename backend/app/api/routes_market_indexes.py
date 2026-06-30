from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.market_index_schema import (
    MarketIndexCollectRequest,
    MarketIndexCollectResponse,
    MarketIndexProviderCodeCollectRequest,
    MarketIndexProviderCodeCollectResponse,
    MarketIndexProviderCodeListResponse,
    MarketIndexSectorCodeAutoMatchResponse,
    MarketIndexCompareResponse,
    MarketIndexDailyPriceListResponse,
    MarketIndexListResponse,
    MarketIndexProviderMappingItem,
    MarketIndexProviderMappingListResponse,
    MarketIndexProviderMappingTestRequest,
    MarketIndexProviderMappingTestResponse,
    MarketIndexProviderMappingUpsertRequest,
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






@router.post("/market-indexes/provider-codes/collect", response_model=MarketIndexProviderCodeCollectResponse)
def collect_market_index_provider_codes(
    payload: MarketIndexProviderCodeCollectRequest,
    db: Session = Depends(get_db),
) -> MarketIndexProviderCodeCollectResponse:
    return MarketIndexService(db).collect_provider_codes(provider=payload.provider, market_types=payload.market_types)


@router.get("/market-indexes/provider-codes", response_model=MarketIndexProviderCodeListResponse)
def list_market_index_provider_codes(
    provider: str = Query(default="KIWOOM_REST"),
    market_type: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> MarketIndexProviderCodeListResponse:
    return MarketIndexService(db).list_provider_codes(provider=provider, market_type=market_type, keyword=keyword)


@router.post("/market-indexes/provider-mappings/auto-match-sector-codes", response_model=MarketIndexSectorCodeAutoMatchResponse)
def auto_match_market_index_sector_codes(
    db: Session = Depends(get_db),
) -> MarketIndexSectorCodeAutoMatchResponse:
    return MarketIndexService(db).auto_match_sector_codes()

@router.get("/market-indexes/provider-mappings", response_model=MarketIndexProviderMappingListResponse)
def list_market_index_provider_mappings(
    db: Session = Depends(get_db),
) -> MarketIndexProviderMappingListResponse:
    return MarketIndexService(db).list_provider_mappings()


@router.put("/market-indexes/{index_code}/provider-mapping", response_model=MarketIndexProviderMappingItem)
def upsert_market_index_provider_mapping(
    index_code: str,
    payload: MarketIndexProviderMappingUpsertRequest,
    db: Session = Depends(get_db),
) -> MarketIndexProviderMappingItem:
    return MarketIndexService(db).upsert_provider_mapping(index_code, payload)


@router.post("/market-indexes/{index_code}/provider-mapping/test", response_model=MarketIndexProviderMappingTestResponse)
def test_market_index_provider_mapping(
    index_code: str,
    payload: MarketIndexProviderMappingTestRequest,
    db: Session = Depends(get_db),
) -> MarketIndexProviderMappingTestResponse:
    return MarketIndexService(db).test_provider_mapping(index_code, payload)


@router.post("/market-indexes/{index_code}/provider-mapping/activate", response_model=MarketIndexProviderMappingItem)
def activate_market_index_provider_mapping(
    index_code: str,
    db: Session = Depends(get_db),
) -> MarketIndexProviderMappingItem:
    return MarketIndexService(db).activate_provider_mapping(index_code)

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
