from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.disclosure_schema import DisclosureBulkDeleteRequest, DisclosureBulkDeleteResponse, DisclosureCollectionTargetResponse, DisclosureResponse
from backend.app.services.disclosure_service import DisclosureService

router = APIRouter()


@router.get("/disclosures/collection-targets", response_model=list[DisclosureCollectionTargetResponse])
def list_disclosure_collection_targets(db: Session = Depends(get_db)) -> list[DisclosureCollectionTargetResponse]:
    return DisclosureService(db).list_collection_targets()


@router.get("/disclosures", response_model=list[DisclosureResponse])
def list_disclosures(
    stock_id: int | None = None,
    keyword: str | None = None,
    disclosure_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[DisclosureResponse]:
    return DisclosureService(db).list_disclosures(
        stock_id=stock_id,
        keyword=keyword,
        disclosure_type=disclosure_type,
        limit=limit,
        offset=offset,
    )


@router.get("/disclosures/{disclosure_id}", response_model=DisclosureResponse)
def get_disclosure(disclosure_id: int, db: Session = Depends(get_db)) -> DisclosureResponse:
    return DisclosureService(db).get_disclosure(disclosure_id)


@router.post("/disclosures/bulk-delete", response_model=DisclosureBulkDeleteResponse)
def delete_disclosures_bulk(payload: DisclosureBulkDeleteRequest, db: Session = Depends(get_db)) -> DisclosureBulkDeleteResponse:
    deleted, failed = DisclosureService(db).delete_disclosures_bulk(payload.disclosure_ids)
    return DisclosureBulkDeleteResponse(deleted=deleted, failed=failed)
