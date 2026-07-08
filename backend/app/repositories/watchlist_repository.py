from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from backend.app.entities.market_theme import MarketTheme
from backend.app.entities.market_theme_stock import MarketThemeStock
from backend.app.entities.stock import Stock
from backend.app.entities.stock_daily_price import StockDailyPrice
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
    ) -> list[tuple[Watchlist, Stock, str | None, str | None, int | None, int | None, str | None]]:
        base_stmt = (
            select(
                Watchlist.id.label("watchlist_id"),
                Stock.id.label("stock_id"),
            )
            .join(Stock, Watchlist.stock_id == Stock.id)
            .order_by(Watchlist.is_active.desc(), Watchlist.registered_at.desc(), Watchlist.id.desc())
        )
        if status:
            base_stmt = base_stmt.where(Watchlist.status == status)
        if market:
            base_stmt = base_stmt.where(Stock.market == market)
        if is_active is not None:
            base_stmt = base_stmt.where(Watchlist.is_active == is_active)
        if keyword:
            keyword_like = f"%{keyword}%"
            base_stmt = base_stmt.where(
                (Stock.stock_code.like(keyword_like))
                | (Stock.stock_name.like(keyword_like))
                | (func.coalesce(Watchlist.interest_reason, "").like(keyword_like))
            )
        base_subq = base_stmt.limit(limit).offset(offset).subquery()

        price_range_subq = (
            select(
                StockDailyPrice.stock_id.label("stock_id"),
                func.min(StockDailyPrice.trade_date).label("price_start_date"),
                func.max(StockDailyPrice.trade_date).label("price_end_date"),
                func.count(StockDailyPrice.id).label("price_data_count"),
            )
            .where(StockDailyPrice.stock_id.in_(select(base_subq.c.stock_id)))
            .group_by(StockDailyPrice.stock_id)
            .subquery()
        )

        theme_rank_subq = (
            select(
                MarketThemeStock.stock_id.label("stock_id"),
                MarketThemeStock.theme_id.label("theme_id"),
                MarketTheme.theme_name.label("theme_name"),
                func.row_number()
                .over(
                    partition_by=MarketThemeStock.stock_id,
                    order_by=(MarketThemeStock.is_primary.desc(), MarketTheme.sort_order.asc(), MarketTheme.theme_name.asc()),
                )
                .label("theme_rank"),
            )
            .join(MarketTheme, MarketThemeStock.theme_id == MarketTheme.id)
            .where(
                MarketThemeStock.is_active == 1,
                MarketTheme.is_active == 1,
                MarketTheme.theme_level == "THEME",
                MarketThemeStock.stock_id.in_(select(base_subq.c.stock_id)),
            )
            .subquery()
        )

        stmt: Select[tuple[Watchlist, Stock, str | None, str | None, int | None, int | None, str | None]] = (
            select(
                Watchlist,
                Stock,
                price_range_subq.c.price_start_date,
                price_range_subq.c.price_end_date,
                price_range_subq.c.price_data_count,
                theme_rank_subq.c.theme_id,
                theme_rank_subq.c.theme_name,
            )
            .join(base_subq, base_subq.c.watchlist_id == Watchlist.id)
            .join(Stock, Watchlist.stock_id == Stock.id)
            .outerjoin(price_range_subq, price_range_subq.c.stock_id == Stock.id)
            .outerjoin(theme_rank_subq, (theme_rank_subq.c.stock_id == Stock.id) & (theme_rank_subq.c.theme_rank == 1))
            .order_by(Watchlist.is_active.desc(), Watchlist.registered_at.desc(), Watchlist.id.desc())
        )
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
