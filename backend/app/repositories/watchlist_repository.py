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
        return self.db.scalar(select(Watchlist).where(Watchlist.stock_id == stock_id))

    def list_with_stock(self, status: str | None, keyword: str | None, limit: int, offset: int) -> list[tuple[Watchlist, str, str]]:
        stmt: Select[tuple[Watchlist, str, str]] = (
            select(Watchlist, Stock.stock_code, Stock.stock_name)
            .join(Stock, Watchlist.stock_id == Stock.id)
            .order_by(Watchlist.id.desc())
        )
        if status:
            stmt = stmt.where(Watchlist.status == status)
        if keyword:
            keyword_like = f"%{keyword}%"
            stmt = stmt.where(
                (Stock.stock_code.like(keyword_like))
                | (Stock.stock_name.like(keyword_like))
                | (func.coalesce(Watchlist.interest_reason, "").like(keyword_like))
            )
        stmt = stmt.limit(limit).offset(offset)
        return list(self.db.execute(stmt).all())

    def update(self, watchlist: Watchlist) -> Watchlist:
        self.db.commit()
        self.db.refresh(watchlist)
        return watchlist

    def delete(self, watchlist: Watchlist) -> None:
        self.db.delete(watchlist)
        self.db.commit()
