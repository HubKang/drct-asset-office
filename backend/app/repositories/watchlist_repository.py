from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from backend.app.entities.stock import Stock
from backend.app.entities.watchlist import Watchlist


class WatchlistRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, watchlist: Watchlist) -> Watchlist:
        self.db.add(watchlist)
        self.db.commit()
        self.db.refresh(watchlist)
        return watchlist

    def get_by_id(self, watchlist_id: int) -> Watchlist | None:
        return self.db.get(Watchlist, watchlist_id)

    def get_by_stock_id(self, stock_id: int) -> Watchlist | None:
        stmt = select(Watchlist).where(Watchlist.stock_id == stock_id).order_by(Watchlist.id.desc())
        return self.db.scalar(stmt)

    def list_with_stock(
        self,
        status: str | None,
        keyword: str | None,
        market: str | None,
        is_active: int | None,
        limit: int,
        offset: int,
    ) -> list[tuple[Watchlist, Stock]]:
        stmt: Select[tuple[Watchlist, Stock]] = (
            select(Watchlist, Stock)
            .join(Stock, Watchlist.stock_id == Stock.id)
            .order_by(Watchlist.is_active.desc(), Watchlist.registered_at.desc(), Watchlist.id.desc())
        )
        if status:
            stmt = stmt.where(Watchlist.status == status)
        if market:
            stmt = stmt.where(Stock.market == market)
        if is_active is not None:
            stmt = stmt.where(Watchlist.is_active == is_active)
        if keyword:
            keyword_like = f"%{keyword}%"
            stmt = stmt.where(
                (Stock.stock_code.like(keyword_like))
                | (Stock.stock_name.like(keyword_like))
                | (func.coalesce(Watchlist.interest_reason, "").like(keyword_like))
            )
        stmt = stmt.limit(limit).offset(offset)
        return list(self.db.execute(stmt).all())

    def list_by_stock_ids(self, stock_ids: list[int]) -> list[Watchlist]:
        if not stock_ids:
            return []
        stmt = select(Watchlist).where(Watchlist.stock_id.in_(stock_ids))
        return list(self.db.scalars(stmt).all())

    def list_active_stock_ids(self) -> list[int]:
        stmt = select(Watchlist.stock_id).where(Watchlist.is_active == 1).order_by(Watchlist.stock_id.asc())
        return [int(stock_id) for stock_id in self.db.scalars(stmt).all()]

    def update(self, watchlist: Watchlist) -> Watchlist:
        self.db.commit()
        self.db.refresh(watchlist)
        return watchlist

    def commit(self) -> None:
        self.db.commit()

    def delete(self, watchlist: Watchlist) -> None:
        self.db.delete(watchlist)
        self.db.commit()
