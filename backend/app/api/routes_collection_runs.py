from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.collection_run_schema import CollectionRunResponse
from backend.app.services.collection_run_service import CollectionRunService

router = APIRouter()


@router.get("/collection-runs", response_model=list[CollectionRunResponse])
def list_collection_runs(
    collector_name: str | None = None,
    status: str | None = None,
    target: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[CollectionRunResponse]:
    return CollectionRunService(db).list_collection_runs(
        collector_name=collector_name,
        status_value=status,
        target=target,
        limit=limit,
        offset=offset,
    )


@router.get("/collection-runs/{run_id}", response_model=CollectionRunResponse)
def get_collection_run(run_id: int, db: Session = Depends(get_db)) -> CollectionRunResponse:
    return CollectionRunService(db).get_collection_run(run_id)
