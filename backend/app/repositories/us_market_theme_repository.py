from __future__ import annotations

from sqlalchemy import case, func, or_, select, text
from sqlalchemy.orm import Session

from backend.app.entities.us_market_theme import UsTheme, UsThemeGroup, UsThemeStock
from backend.app.entities.us_stock import UsStock


class UsMarketThemeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_group(self, group_id: int) -> UsThemeGroup | None:
        return self.db.get(UsThemeGroup, group_id)

    def get_theme(self, theme_id: int) -> UsTheme | None:
        return self.db.get(UsTheme, theme_id)

    def get_mapping(self, mapping_id: int) -> UsThemeStock | None:
        return self.db.get(UsThemeStock, mapping_id)

    def get_mapping_by_pair(self, theme_id: int, stock_id: int) -> UsThemeStock | None:
        return self.db.scalar(select(UsThemeStock).where(UsThemeStock.theme_id == theme_id, UsThemeStock.us_stock_id == stock_id))

    def list_groups(self) -> list[tuple[UsThemeGroup, int, int, int]]:
        counts = (
            select(
                UsTheme.theme_group_id.label("group_id"),
                func.count(UsTheme.id).label("theme_count"),
                func.sum(case((UsTheme.active == 1, 1), else_=0)).label("active_theme_count"),
                func.count(func.distinct(case((UsThemeStock.active == 1, UsThemeStock.us_stock_id), else_=None))).label("linked_stock_count"),
            )
            .outerjoin(UsThemeStock, UsThemeStock.theme_id == UsTheme.id)
            .group_by(UsTheme.theme_group_id)
            .subquery()
        )
        rows = self.db.execute(
            select(UsThemeGroup, counts.c.theme_count, counts.c.active_theme_count, counts.c.linked_stock_count)
            .outerjoin(counts, counts.c.group_id == UsThemeGroup.id)
            .order_by(UsThemeGroup.active.desc(), UsThemeGroup.sort_order.asc(), UsThemeGroup.name.asc())
        ).all()
        return [(group, int(total or 0), int(active or 0), int(linked or 0)) for group, total, active, linked in rows]

    def list_themes(self, *, group_id: int | None = None, active: int | None = None, keyword: str | None = None) -> list[tuple[UsTheme, str, int, str | None]]:
        filters = []
        if group_id is not None:
            filters.append(UsTheme.theme_group_id == group_id)
        if active is not None:
            filters.append(UsTheme.active == active)
        if keyword:
            term = f"%{keyword.strip()}%"
            filters.append(or_(UsTheme.name.like(term), UsTheme.keywords.like(term), UsThemeGroup.name.like(term)))
        rows = self.db.execute(
            select(
                UsTheme,
                UsThemeGroup.name,
                func.count(case((UsThemeStock.active == 1, UsThemeStock.id), else_=None)),
                func.group_concat(case((UsThemeStock.is_representative == 1, UsStock.symbol), else_=None), ","),
            )
            .join(UsThemeGroup, UsThemeGroup.id == UsTheme.theme_group_id)
            .outerjoin(UsThemeStock, UsThemeStock.theme_id == UsTheme.id)
            .outerjoin(UsStock, UsStock.id == UsThemeStock.us_stock_id)
            .where(*filters)
            .group_by(UsTheme.id, UsThemeGroup.name)
            .order_by(UsTheme.active.desc(), UsThemeGroup.sort_order.asc(), UsTheme.sort_order.asc(), UsTheme.name.asc())
        ).all()
        return [(theme, group_name, int(linked or 0), representatives) for theme, group_name, linked, representatives in rows]

    def list_theme_stocks(self, theme_id: int, *, active_only: bool = True) -> list[tuple[UsThemeStock, UsStock]]:
        stmt = select(UsThemeStock, UsStock).join(UsStock, UsStock.id == UsThemeStock.us_stock_id).where(UsThemeStock.theme_id == theme_id)
        if active_only:
            stmt = stmt.where(UsThemeStock.active == 1)
        return list(self.db.execute(stmt.order_by(UsThemeStock.sort_order.asc(), UsStock.symbol.asc())).all())

    def summary(self) -> dict[str, int]:
        group_count = int(self.db.scalar(select(func.count()).select_from(UsThemeGroup)) or 0)
        theme_count, active_count = self.db.execute(select(func.count(UsTheme.id), func.sum(case((UsTheme.active == 1, 1), else_=0)))).one()
        linked = self.db.scalar(
            select(func.count(func.distinct(UsThemeStock.us_stock_id)))
            .join(UsTheme, UsTheme.id == UsThemeStock.theme_id)
            .where(UsThemeStock.active == 1, UsTheme.active == 1)
        )
        return {"theme_groups": group_count, "themes": int(theme_count or 0), "active_themes": int(active_count or 0), "linked_stocks": int(linked or 0)}

    def latest_returns(self, theme_ids: list[int]) -> dict[int, dict[str, object]]:
        if not theme_ids:
            return {}
        placeholders = ",".join(f":theme_{index}" for index, _ in enumerate(theme_ids))
        params = {f"theme_{index}": theme_id for index, theme_id in enumerate(theme_ids)}
        rows = self.db.execute(text(f"""
            SELECT r.theme_id,r.trade_date,r.simple_return,r.theme_strength,r.breadth_ratio
            FROM us_theme_daily_returns r
            WHERE r.theme_id IN ({placeholders})
              AND r.trade_date=(SELECT MAX(r2.trade_date) FROM us_theme_daily_returns r2 WHERE r2.theme_id=r.theme_id)
        """), params).mappings().all()
        return {int(row["theme_id"]): dict(row) for row in rows}

    def save(self, row):
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row
