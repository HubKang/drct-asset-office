from __future__ import annotations

import json

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from backend.app.entities.market_theme import MarketTheme
from backend.app.entities.market_theme_stock import MarketThemeStock


class MarketThemeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, row: MarketTheme) -> MarketTheme:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_by_id(self, theme_id: int) -> MarketTheme | None:
        return self.db.get(MarketTheme, theme_id)

    def get_by_theme_code(self, theme_code: str) -> MarketTheme | None:
        stmt = select(MarketTheme).where(MarketTheme.theme_code == theme_code)
        return self.db.scalar(stmt)

    def update(self, row: MarketTheme) -> MarketTheme:
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_with_stock_count(
        self,
        *,
        is_active: int | None,
        theme_type: str | None,
        theme_level: str | None,
        parent_theme_id: int | None,
        is_supply_theme: int | None,
        keyword: str | None,
        limit: int,
        offset: int,
    ) -> list[tuple[MarketTheme, int]]:
        stock_count_subquery = (
            select(
                MarketThemeStock.theme_id.label("theme_id"),
                func.count(MarketThemeStock.id).label("stock_count"),
            )
            .where(MarketThemeStock.is_active == 1)
            .group_by(MarketThemeStock.theme_id)
            .subquery()
        )

        stmt: Select[tuple[MarketTheme, int]] = (
            select(
                MarketTheme,
                func.coalesce(stock_count_subquery.c.stock_count, 0),
            )
            .outerjoin(stock_count_subquery, stock_count_subquery.c.theme_id == MarketTheme.id)
            .order_by(
                MarketTheme.is_supply_theme.desc(),
                MarketTheme.sort_order.asc(),
                MarketTheme.theme_name.asc(),
            )
        )
        if is_active is not None:
            stmt = stmt.where(MarketTheme.is_active == is_active)
        if theme_type:
            stmt = stmt.where(MarketTheme.theme_type == theme_type)
        if theme_level:
            stmt = stmt.where(MarketTheme.theme_level == theme_level)
        if parent_theme_id is not None:
            stmt = stmt.where(MarketTheme.parent_theme_id == parent_theme_id)
        if is_supply_theme is not None:
            stmt = stmt.where(MarketTheme.is_supply_theme == is_supply_theme)
        if keyword:
            keyword_like = f"%{keyword}%"
            stmt = stmt.where(
                (MarketTheme.theme_name.like(keyword_like))
                | (MarketTheme.theme_code.like(keyword_like))
                | (func.coalesce(MarketTheme.description, "").like(keyword_like))
                | (func.coalesce(MarketTheme.keywords, "").like(keyword_like))
            )
        stmt = stmt.limit(limit).offset(offset)
        return list(self.db.execute(stmt).all())

    def list_all_with_stock_count(self) -> list[tuple[MarketTheme, int]]:
        return self.list_with_stock_count(
            is_active=None,
            theme_type=None,
            theme_level=None,
            parent_theme_id=None,
            is_supply_theme=None,
            keyword=None,
            limit=10000,
            offset=0,
        )

    def get_stock_count(self, theme_id: int) -> int:
        stmt = select(func.count(MarketThemeStock.id)).where(
            MarketThemeStock.theme_id == theme_id,
            MarketThemeStock.is_active == 1,
        )
        return int(self.db.scalar(stmt) or 0)

    def get_with_stock_count(self, theme_id: int) -> tuple[MarketTheme, int] | None:
        stock_count_subquery = (
            select(
                MarketThemeStock.theme_id.label("theme_id"),
                func.count(MarketThemeStock.id).label("stock_count"),
            )
            .where(MarketThemeStock.is_active == 1)
            .group_by(MarketThemeStock.theme_id)
            .subquery()
        )
        stmt = (
            select(MarketTheme, func.coalesce(stock_count_subquery.c.stock_count, 0))
            .outerjoin(stock_count_subquery, stock_count_subquery.c.theme_id == MarketTheme.id)
            .where(MarketTheme.id == theme_id)
        )
        row = self.db.execute(stmt).first()
        if not row:
            return None
        return row[0], int(row[1])

    @staticmethod
    def parse_keywords(raw: str | None) -> list[str]:
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            return []
        return []
