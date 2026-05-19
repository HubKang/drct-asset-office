from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.entities.market_theme_stock import MarketThemeStock
from backend.app.repositories.market_theme_repository import MarketThemeRepository
from backend.app.repositories.market_theme_stock_repository import MarketThemeStockRepository
from backend.app.repositories.stock_repository import StockRepository
from backend.app.schemas.market_theme_stock_schema import (
    MarketThemeStockCreateRequest,
    MarketThemeStockResponse,
    MarketThemeStockUpdateRequest,
)


class MarketThemeStockService:
    def __init__(self, db: Session) -> None:
        self.repo = MarketThemeStockRepository(db)
        self.theme_repo = MarketThemeRepository(db)
        self.stock_repo = StockRepository(db)

    @staticmethod
    def _to_response(row: MarketThemeStock, stock_code: str, stock_name: str, market: str | None) -> MarketThemeStockResponse:
        return MarketThemeStockResponse(
            mapping_id=row.id,
            theme_id=row.theme_id,
            stock_id=row.stock_id,
            stock_code=stock_code,
            stock_name=stock_name,
            market=market,
            mapping_source=row.mapping_source,
            confidence_score=row.confidence_score,
            is_primary=row.is_primary,
            is_active=row.is_active,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def list_theme_stocks(self, theme_id: int) -> list[MarketThemeStockResponse]:
        theme = self.theme_repo.get_by_id(theme_id)
        if not theme:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="market theme not found")
        rows = self.repo.list_with_stock(theme_id)
        return [
            self._to_response(mapping, stock.stock_code, stock.stock_name, stock.market)
            for mapping, stock in rows
        ]

    def create_theme_stock(self, theme_id: int, payload: MarketThemeStockCreateRequest) -> MarketThemeStockResponse:
        theme = self.theme_repo.get_by_id(theme_id)
        if not theme:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="market theme not found")
        stock = self.stock_repo.get_by_id(payload.stock_id)
        if not stock:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="stock not found")

        existing = self.repo.get_by_theme_stock(theme_id, payload.stock_id)
        now = now_kst()
        if existing and existing.is_active == 1:
            return self._to_response(existing, stock.stock_code, stock.stock_name, stock.market)
        if existing and existing.is_active == 0:
            existing.is_active = 1
            existing.is_primary = 1 if payload.is_primary else 0
            existing.mapping_source = existing.mapping_source or "manual"
            existing.confidence_score = existing.confidence_score if existing.confidence_score is not None else 1.0
            existing.updated_at = now
            updated = self.repo.update(existing)
            return self._to_response(updated, stock.stock_code, stock.stock_name, stock.market)

        row = MarketThemeStock(
            theme_id=theme_id,
            stock_id=payload.stock_id,
            mapping_source="manual",
            confidence_score=1.0,
            is_primary=1 if payload.is_primary else 0,
            is_active=1,
            created_at=now,
            updated_at=now,
        )
        created = self.repo.create(row)
        return self._to_response(created, stock.stock_code, stock.stock_name, stock.market)

    def update_theme_stock(self, mapping_id: int, payload: MarketThemeStockUpdateRequest) -> MarketThemeStockResponse:
        row = self.repo.get_by_id(mapping_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="market theme stock mapping not found")
        stock = self.stock_repo.get_by_id(row.stock_id)
        if not stock:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="stock not found")

        data = payload.model_dump(exclude_unset=True)
        if "is_primary" in data and data["is_primary"] is not None:
            row.is_primary = 1 if data["is_primary"] else 0
        if "is_active" in data and data["is_active"] is not None:
            row.is_active = 1 if data["is_active"] else 0
        if "confidence_score" in data:
            row.confidence_score = data["confidence_score"]
        row.updated_at = now_kst()
        updated = self.repo.update(row)
        return self._to_response(updated, stock.stock_code, stock.stock_name, stock.market)

    def deactivate_theme_stock(self, mapping_id: int) -> MarketThemeStockResponse:
        row = self.repo.get_by_id(mapping_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="market theme stock mapping not found")
        stock = self.stock_repo.get_by_id(row.stock_id)
        if not stock:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="stock not found")
        row.is_active = 0
        row.updated_at = now_kst()
        updated = self.repo.update(row)
        return self._to_response(updated, stock.stock_code, stock.stock_name, stock.market)

