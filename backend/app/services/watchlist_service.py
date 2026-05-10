from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.entities.watchlist import Watchlist
from backend.app.repositories.stock_repository import StockRepository
from backend.app.repositories.watchlist_repository import WatchlistRepository
from backend.app.schemas.watchlist_schema import WatchlistCreate, WatchlistListItem, WatchlistUpdate


class WatchlistService:
    def __init__(self, db: Session) -> None:
        self.repo = WatchlistRepository(db)
        self.stock_repo = StockRepository(db)

    def create_watchlist(self, payload: WatchlistCreate) -> Watchlist:
        stock = self.stock_repo.get_by_id(payload.stock_id)
        if not stock:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="stock not found")
        if stock.is_active == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="inactive stock cannot be added to watchlist",
            )
        if self.repo.get_by_stock_id(payload.stock_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="stock already exists in watchlist")
        now = now_kst()
        item = Watchlist(
            stock_id=payload.stock_id,
            status=payload.status.value,
            interest_reason=payload.interest_reason,
            entry_condition=payload.entry_condition,
            exit_condition=payload.exit_condition,
            risk_note=payload.risk_note,
            registered_at=now,
            updated_at=now,
        )
        return self.repo.create(item)

    def list_watchlist(self, status_filter: str | None, keyword: str | None, limit: int, offset: int) -> list[WatchlistListItem]:
        rows = self.repo.list_with_stock(status=status_filter, keyword=keyword, limit=limit, offset=offset)
        return [
            WatchlistListItem(
                id=item.id,
                stock_id=item.stock_id,
                stock_code=stock_code,
                stock_name=stock_name,
                status=item.status,
                interest_reason=item.interest_reason,
                entry_condition=item.entry_condition,
                exit_condition=item.exit_condition,
                risk_note=item.risk_note,
                registered_at=item.registered_at,
                updated_at=item.updated_at,
            )
            for item, stock_code, stock_name in rows
        ]

    def get_watchlist(self, watchlist_id: int) -> Watchlist:
        item = self.repo.get_by_id(watchlist_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="watchlist not found")
        return item

    def update_watchlist(self, watchlist_id: int, payload: WatchlistUpdate) -> Watchlist:
        item = self.get_watchlist(watchlist_id)
        data = payload.model_dump(exclude_unset=True)
        if "status" in data and data["status"] is not None:
            data["status"] = data["status"].value
        for key, value in data.items():
            setattr(item, key, value)
        item.updated_at = now_kst()
        return self.repo.update(item)

    def delete_watchlist(self, watchlist_id: int) -> None:
        item = self.get_watchlist(watchlist_id)
        self.repo.delete(item)
