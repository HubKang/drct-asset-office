from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.watchlist_schema import (
    WatchlistCreate,
    WatchlistListItem,
    WatchlistResponse,
    WatchlistUpdate,
)
from backend.app.services.watchlist_service import WatchlistService

router = APIRouter()


@router.post("/watchlist", response_model=WatchlistResponse, status_code=status.HTTP_201_CREATED)
def create_watchlist(payload: WatchlistCreate, db: Session = Depends(get_db)) -> WatchlistResponse:
    return WatchlistService(db).create_watchlist(payload)


@router.get("/watchlist", response_model=list[WatchlistListItem])
def list_watchlist(
    status_filter: str | None = Query(default=None, alias="status"),
    keyword: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[WatchlistListItem]:
    return WatchlistService(db).list_watchlist(status_filter=status_filter, keyword=keyword, limit=limit, offset=offset)


@router.get("/watchlist/{watchlist_id}", response_model=WatchlistResponse)
def get_watchlist(watchlist_id: int, db: Session = Depends(get_db)) -> WatchlistResponse:
    return WatchlistService(db).get_watchlist(watchlist_id)


@router.put("/watchlist/{watchlist_id}", response_model=WatchlistResponse)
def update_watchlist(watchlist_id: int, payload: WatchlistUpdate, db: Session = Depends(get_db)) -> WatchlistResponse:
    return WatchlistService(db).update_watchlist(watchlist_id, payload)


@router.delete("/watchlist/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watchlist(watchlist_id: int, db: Session = Depends(get_db)) -> None:
    WatchlistService(db).delete_watchlist(watchlist_id)
    return None
