from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from backend.app.entities.stock import Stock


class StockRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, stock: Stock) -> Stock:
        self.db.add(stock)
        self.db.commit()
        self.db.refresh(stock)
        return stock

    def get_by_id(self, stock_id: int) -> Stock | None:
        return self.db.get(Stock, stock_id)

    def get_by_code(self, stock_code: str) -> Stock | None:
        return self.db.scalar(select(Stock).where(Stock.stock_code == stock_code))

    def list_a_prefix_codes(self) -> list[Stock]:
        stmt: Select[tuple[Stock]] = (
            select(Stock)
            .where(Stock.stock_code.like("A______"))
            .order_by(Stock.stock_code.asc(), Stock.id.asc())
        )
        return list(self.db.scalars(stmt).all())

    def list(
        self,
        keyword: str | None,
        is_active: int | None,
        market: str | None = None,
        security_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Stock]:
        stmt: Select[tuple[Stock]] = select(Stock)
        if keyword:
            keyword_like = f"%{keyword}%"
            stmt = stmt.where((Stock.stock_code.like(keyword_like)) | (Stock.stock_name.like(keyword_like)))
        if is_active is not None:
            stmt = stmt.where(Stock.is_active == is_active)
        if market:
            stmt = stmt.where(Stock.market == market)
        if security_type:
            stmt = stmt.where(Stock.security_type == security_type)
        stmt = stmt.order_by(Stock.id.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt).all())

    def update(self, stock: Stock) -> Stock:
        self.db.commit()
        self.db.refresh(stock)
        return stock

    def list_by_market(self, market: str) -> list[Stock]:
        stmt: Select[tuple[Stock]] = select(Stock).where(Stock.market == market).order_by(Stock.id.desc())
        return list(self.db.scalars(stmt).all())

    def list_active_by_market(self, market: str, security_types: list[str] | None = None) -> list[Stock]:
        stmt: Select[tuple[Stock]] = select(Stock).where(Stock.market == market, Stock.is_active == 1)
        if security_types:
            stmt = stmt.where(Stock.security_type.in_(security_types))
        stmt = stmt.order_by(Stock.id.desc())
        return list(self.db.scalars(stmt).all())

    def get_by_codes(self, codes: list[str]) -> list[Stock]:
        if not codes:
            return []
        result: list[Stock] = []
        chunk_size = 500
        for i in range(0, len(codes), chunk_size):
            chunk = codes[i : i + chunk_size]
            stmt: Select[tuple[Stock]] = select(Stock).where(Stock.stock_code.in_(chunk))
            result.extend(list(self.db.scalars(stmt).all()))
        return result

    def flush(self) -> None:
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()
