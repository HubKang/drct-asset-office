from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.entities.watchlist import Watchlist
from backend.app.repositories.stock_repository import StockRepository
from backend.app.repositories.watchlist_repository import WatchlistRepository
from backend.app.schemas.watchlist_schema import (
    WatchlistBulkCreate,
    WatchlistBulkCreateResponse,
    WatchlistCreate,
    WatchlistListItem,
    WatchlistStockIdsResponse,
    WatchlistUpdate,
)


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

        existing = self.repo.get_by_stock_id(payload.stock_id)
        if existing and existing.is_active == 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="stock already exists in watchlist")

        now = now_kst()
        if existing and existing.is_active == 0:
            existing.status = payload.status.value
            existing.interest_reason = payload.interest_reason
            existing.entry_condition = payload.entry_condition
            existing.exit_condition = payload.exit_condition
            existing.risk_note = payload.risk_note
            existing.is_active = 1
            existing.updated_at = now
            return self.repo.update(existing)

        item = Watchlist(
            stock_id=payload.stock_id,
            status=payload.status.value,
            interest_reason=payload.interest_reason,
            entry_condition=payload.entry_condition,
            exit_condition=payload.exit_condition,
            risk_note=payload.risk_note,
            is_active=1,
            registered_at=now,
            updated_at=now,
        )
        return self.repo.create(item)

    def list_watchlist(
        self,
        status_filter: str | None,
        keyword: str | None,
        market: str | None,
        is_active: int | None,
        limit: int,
        offset: int,
    ) -> list[WatchlistListItem]:
        rows = self.repo.list_with_stock(
            status=status_filter,
            keyword=keyword,
            market=market,
            is_active=is_active,
            limit=limit,
            offset=offset,
        )
        return [
            WatchlistListItem(
                id=item.id,
                stock_id=item.stock_id,
                stock_code=stock.stock_code,
                stock_name=stock.stock_name,
                market=stock.market,
                security_type=stock.security_type,
                status=item.status,
                interest_reason=item.interest_reason,
                entry_condition=item.entry_condition,
                exit_condition=item.exit_condition,
                risk_note=item.risk_note,
                is_active=item.is_active,
                price_start_date=price_start_date,
                price_end_date=price_end_date,
                price_data_count=int(price_data_count) if price_data_count is not None else None,
                primary_theme_id=int(primary_theme_id) if primary_theme_id is not None else None,
                primary_theme_name=primary_theme_name,
                registered_at=item.registered_at,
                updated_at=item.updated_at,
            )
            for item, stock, price_start_date, price_end_date, price_data_count, primary_theme_id, primary_theme_name in rows
        ]

    def get_watchlist_stock_ids(self) -> WatchlistStockIdsResponse:
        return WatchlistStockIdsResponse(stock_ids=self.repo.list_active_stock_ids())

    def bulk_create_watchlist(self, payload: WatchlistBulkCreate) -> WatchlistBulkCreateResponse:
        stock_ids = list(dict.fromkeys(payload.stock_ids))
        if not stock_ids:
            return WatchlistBulkCreateResponse(
                requested_count=0,
                inserted_count=0,
                reactivated_count=0,
                skipped_count=0,
                message="no stock ids requested",
            )

        existing_map = {item.stock_id: item for item in self.repo.list_by_stock_ids(stock_ids)}
        now = now_kst()
        inserted_count = 0
        reactivated_count = 0
        skipped_count = 0

        for stock_id in stock_ids:
            stock = self.stock_repo.get_by_id(stock_id)
            if not stock or stock.is_active == 0:
                skipped_count += 1
                continue

            existing = existing_map.get(stock_id)
            if existing and existing.is_active == 1:
                skipped_count += 1
                continue

            if existing and existing.is_active == 0:
                existing.is_active = 1
                existing.updated_at = now
                if payload.memo and not existing.interest_reason:
                    existing.interest_reason = payload.memo
                reactivated_count += 1
                continue

            self.repo.db.add(
                Watchlist(
                    stock_id=stock_id,
                    status="\uad00\uc2ec",
                    interest_reason=payload.memo,
                    entry_condition=None,
                    exit_condition=None,
                    risk_note=None,
                    is_active=1,
                    registered_at=now,
                    updated_at=now,
                )
            )
            inserted_count += 1

        self.repo.commit()
        return WatchlistBulkCreateResponse(
            requested_count=len(stock_ids),
            inserted_count=inserted_count,
            reactivated_count=reactivated_count,
            skipped_count=skipped_count,
            message=(
                f"\uad00\uc2ec\uc885\ubaa9 {inserted_count}\uac74 \ucd94\uac00, "
                f"{reactivated_count}\uac74 \uc7ac\ud65c\uc131\ud654, {skipped_count}\uac74 \uac74\ub108\ub700"
            ),
        )

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
        if "is_active" in data and data["is_active"] is not None:
            data["is_active"] = 1 if data["is_active"] else 0
        for key, value in data.items():
            setattr(item, key, value)
        item.updated_at = now_kst()
        return self.repo.update(item)

    def delete_watchlist(self, watchlist_id: int) -> None:
        item = self.get_watchlist(watchlist_id)
        if item.is_active == 0:
            return
        item.is_active = 0
        item.updated_at = now_kst()
        self.repo.update(item)
