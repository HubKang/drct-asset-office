from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.market_indicator_schema import (
    EcosDiscoverCandidatesRequest,
    EcosDiscoverCandidatesResponse,
    EcosDiscoverMappingCandidatesRequest,
    EcosDiscoverMappingCandidatesResponse,
    EcosItemListResponse,
    EcosMappingCandidateTestRequest,
    EcosTableListResponse,
    EcosTableSearchResponse,
    ExternalProviderStatusListResponse,
    MarketIndicator,
    MarketIndicatorCollectRequest,
    MarketIndicatorCollectResponse,
    MarketIndicatorListResponse,
    MarketIndicatorProviderMapping,
    MarketIndicatorProviderMappingListResponse,
    MarketIndicatorProviderMappingTestRequest,
    MarketIndicatorProviderMappingTestResponse,
    MarketIndicatorProviderMappingUpsertRequest,
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




@router.get("/market-indicators-data/ecos/table-list", response_model=EcosTableListResponse)
def list_bok_ecos_table_list(
    parent_stat_code: str | None = Query(default=None),
    start_index: int = Query(default=1, ge=1),
    end_index: int = Query(default=100, ge=1),
    db: Session = Depends(get_db),
) -> EcosTableListResponse:
    return MarketIndicatorService(db).get_ecos_table_list(parent_stat_code=parent_stat_code, start_index=start_index, end_index=end_index)


@router.get("/market-indicators-data/ecos/table-search", response_model=EcosTableSearchResponse)
def search_bok_ecos_table_list(
    keyword: str = Query(...),
    parent_stat_code: str | None = Query(default=None),
    cycle: str | None = Query(default=None),
    only_searchable: bool = Query(default=False),
    max_depth: int = Query(default=2, ge=0, le=4),
    db: Session = Depends(get_db),
) -> EcosTableSearchResponse:
    return MarketIndicatorService(db).search_ecos_tables(keyword=keyword, parent_stat_code=parent_stat_code, cycle=cycle, only_searchable=only_searchable, max_depth=max_depth)


@router.post("/market-indicators-data/ecos/discover-candidates", response_model=EcosDiscoverCandidatesResponse)
def discover_bok_ecos_candidates(
    payload: EcosDiscoverCandidatesRequest,
    db: Session = Depends(get_db),
) -> EcosDiscoverCandidatesResponse:
    return MarketIndicatorService(db).discover_ecos_candidates(payload)


@router.post("/market-indicators-data/ecos/discover-mapping-candidates", response_model=EcosDiscoverMappingCandidatesResponse)
def discover_bok_ecos_mapping_candidates(
    payload: EcosDiscoverMappingCandidatesRequest,
    db: Session = Depends(get_db),
) -> EcosDiscoverMappingCandidatesResponse:
    return MarketIndicatorService(db).discover_ecos_mapping_candidates(payload)


@router.get("/market-indicators-data/ecos/item-list", response_model=EcosItemListResponse)
def list_bok_ecos_item_list(
    stat_code: str = Query(...),
    start_index: int = Query(default=1, ge=1),
    end_index: int = Query(default=100, ge=1),
    db: Session = Depends(get_db),
) -> EcosItemListResponse:
    return MarketIndicatorService(db).get_ecos_item_list(stat_code, start_index=start_index, end_index=end_index)


@router.post("/market-indicators-data/{indicator_code}/provider-mapping/test-candidate", response_model=MarketIndicatorProviderMappingTestResponse)
def test_market_indicator_provider_mapping_candidate(
    indicator_code: str,
    payload: EcosMappingCandidateTestRequest,
    db: Session = Depends(get_db),
) -> MarketIndicatorProviderMappingTestResponse:
    return MarketIndicatorService(db).test_ecos_mapping_candidate(indicator_code, payload)


@router.put("/market-indicators-data/{indicator_code}/provider-mapping", response_model=MarketIndicatorProviderMapping)
def upsert_market_indicator_provider_mapping(
    indicator_code: str,
    payload: MarketIndicatorProviderMappingUpsertRequest,
    db: Session = Depends(get_db),
) -> MarketIndicatorProviderMapping:
    return MarketIndicatorService(db).upsert_provider_mapping(indicator_code, payload)


@router.post("/market-indicators-data/{indicator_code}/provider-mapping/test", response_model=MarketIndicatorProviderMappingTestResponse)
def test_market_indicator_provider_mapping(
    indicator_code: str,
    payload: MarketIndicatorProviderMappingTestRequest,
    db: Session = Depends(get_db),
) -> MarketIndicatorProviderMappingTestResponse:
    return MarketIndicatorService(db).test_provider_mapping(indicator_code, payload)


@router.post("/market-indicators-data/{indicator_code}/provider-mapping/activate", response_model=MarketIndicatorProviderMapping)
def activate_market_indicator_provider_mapping(
    indicator_code: str,
    db: Session = Depends(get_db),
) -> MarketIndicatorProviderMapping:
    return MarketIndicatorService(db).activate_provider_mapping(indicator_code)


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
    return MarketIndicatorService(db).collect_indicator(payload.indicator_codes, start_date=payload.start_date, end_date=payload.end_date)
