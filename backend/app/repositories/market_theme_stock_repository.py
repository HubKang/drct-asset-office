from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from backend.app.entities.market_theme import MarketTheme
from backend.app.entities.market_theme_stock import MarketThemeStock
from backend.app.entities.stock import Stock


class MarketThemeStockRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, row: MarketThemeStock) -> MarketThemeStock:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_by_id(self, mapping_id: int) -> MarketThemeStock | None:
        return self.db.get(MarketThemeStock, mapping_id)

    def get_by_theme_stock(self, theme_id: int, stock_id: int) -> MarketThemeStock | None:
        stmt = select(MarketThemeStock).where(
            MarketThemeStock.theme_id == theme_id,
            MarketThemeStock.stock_id == stock_id,
        )
        return self.db.scalar(stmt)

    def update(self, row: MarketThemeStock) -> MarketThemeStock:
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_with_stock(self, theme_id: int) -> list[tuple[MarketThemeStock, Stock]]:
        stmt: Select[tuple[MarketThemeStock, Stock]] = (
            select(MarketThemeStock, Stock)
            .join(Stock, Stock.id == MarketThemeStock.stock_id)
            .where(MarketThemeStock.theme_id == theme_id)
            .order_by(MarketThemeStock.is_active.desc(), MarketThemeStock.is_primary.desc(), Stock.stock_name.asc())
        )
        return list(self.db.execute(stmt).all())

    def list_themes_by_stock_code(self, stock_code: str) -> list[tuple[MarketThemeStock, MarketTheme, Stock]]:
        normalized = (stock_code or "").strip()
        if not normalized:
            return []
        stmt: Select[tuple[MarketThemeStock, MarketTheme, Stock]] = (
            select(MarketThemeStock, MarketTheme, Stock)
            .join(Stock, Stock.id == MarketThemeStock.stock_id)
            .join(MarketTheme, MarketTheme.id == MarketThemeStock.theme_id)
            .where(
                Stock.stock_code == normalized,
                Stock.is_active == 1,
                MarketThemeStock.is_active == 1,
                MarketTheme.is_active == 1,
            )
            .order_by(MarketThemeStock.is_primary.desc(), MarketTheme.sort_order.asc(), MarketTheme.theme_name.asc())
        )
        return list(self.db.execute(stmt).all())
