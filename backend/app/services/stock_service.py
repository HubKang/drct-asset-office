from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.entities.stock import Stock
from backend.app.repositories.stock_repository import StockRepository
from backend.app.schemas.stock_schema import StockCreate, StockUpdate


class StockService:
    def __init__(self, db: Session) -> None:
        self.repo = StockRepository(db)

    def create_stock(self, payload: StockCreate) -> Stock:
        if self.repo.get_by_code(payload.stock_code):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="stock_code already exists")
        now = now_kst()
        stock = Stock(
            stock_code=payload.stock_code,
            stock_name=payload.stock_name,
            market=payload.market,
            sector=payload.sector,
            industry=payload.industry,
            security_type=payload.security_type,
            is_active=1,
            created_at=now,
            updated_at=now,
        )
        try:
            return self.repo.create(stock)
        except IntegrityError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid stock payload") from exc

    def list_stocks(
        self,
        keyword: str | None,
        is_active: int | None,
        market: str | None,
        security_type: str | None,
        limit: int,
        offset: int,
    ) -> list[Stock]:
        return self.repo.list(
            keyword=keyword,
            is_active=is_active,
            market=market,
            security_type=security_type,
            limit=limit,
            offset=offset,
        )

    def get_stock(self, stock_id: int) -> Stock:
        stock = self.repo.get_by_id(stock_id)
        if not stock:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="stock not found")
        return stock

    def update_stock(self, stock_id: int, payload: StockUpdate) -> Stock:
        stock = self.get_stock(stock_id)
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(stock, key, value)
        stock.updated_at = now_kst()
        return self.repo.update(stock)

    def deactivate_stock(self, stock_id: int) -> Stock:
        stock = self.get_stock(stock_id)
        stock.is_active = 0
        stock.updated_at = now_kst()
        return self.repo.update(stock)
