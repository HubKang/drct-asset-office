from __future__ import annotations

from datetime import date, timedelta
import logging

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.entities.market_theme_stock import MarketThemeStock
from backend.app.repositories.market_theme_repository import MarketThemeRepository
from backend.app.repositories.market_theme_stock_repository import MarketThemeStockRepository
from backend.app.repositories.stock_repository import StockRepository
from backend.app.schemas.market_theme_stock_schema import (
    MarketThemeByStockItem,
    MarketThemeByStockResponse,
    MarketThemeStockMemoItem,
    MarketThemeStockMemoResponse,
    MarketThemeStockCreateRequest,
    MarketThemeStockResponse,
    MarketThemeStockSupplySummaryResponse,
    MarketThemeStockUpdateRequest,
)
from backend.app.utils.stock_code import normalize_stock_code

logger = logging.getLogger(__name__)


class MarketThemeStockService:
    def __init__(self, db: Session) -> None:
        self.db = db
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

    @staticmethod
    def _date_window(as_of_date: date | None = None) -> tuple[str, str]:
        end = as_of_date or date.fromisoformat(now_kst()[:10])
        return end.isoformat(), (end - timedelta(days=29)).isoformat()

    def list_theme_stocks(
        self,
        theme_id: int,
        *,
        as_of_date: date | None = None,
    ) -> list[MarketThemeStockResponse]:
        theme = self.theme_repo.get_by_id(theme_id)
        if not theme:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="market theme not found")
        end_date, recent_start_date = self._date_window(as_of_date)
        rows = self.repo.list_with_supply_summary(
            theme_id,
            as_of_date=end_date,
            recent_start_date=recent_start_date,
        )
        return [MarketThemeStockResponse(**row) for row in rows]

    def get_supply_summary(
        self,
        theme_id: int,
        stock_id: int,
        *,
        as_of_date: date | None = None,
    ) -> MarketThemeStockSupplySummaryResponse:
        end_date, recent_start_date = self._date_window(as_of_date)
        row = self.repo.get_supply_summary(
            theme_id,
            stock_id,
            as_of_date=end_date,
            recent_start_date=recent_start_date,
        )
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="market theme or stock not found")
        response = MarketThemeStockSupplySummaryResponse(**row)
        logger.info(
            "[THEME CONTEXT SUPPLY HISTORY] stock_code=%s current_theme=%s linked_themes=%s current_theme_dates=%s overall_stock_dates=%s memo_count=%s",
            response.stock_code,
            response.current_theme.theme_name,
            ",".join(f"{item.theme_name}:{item.supply_count}" for item in response.linked_theme_supply_summaries),
            response.current_theme_supply_dates,
            response.overall_stock_supply_dates,
            len(response.stock_memos),
        )
        return response

    def create_theme_stock(self, theme_id: int, payload: MarketThemeStockCreateRequest) -> MarketThemeStockResponse:
        theme = self.theme_repo.get_by_id(theme_id)
        if not theme:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="market theme not found")
        if (theme.theme_level or "THEME") == "THEME_GROUP":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="종목은 테마에만 연결할 수 있습니다.")
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

    def list_themes_by_stock_code(self, stock_code: str) -> MarketThemeByStockResponse:
        rows = self.repo.list_themes_by_stock_code(stock_code)
        stock_name = None
        themes: list[MarketThemeByStockItem] = []
        for mapping, theme, stock in rows:
            stock_name = stock.stock_name
            themes.append(
                MarketThemeByStockItem(
                    theme_id=theme.id,
                    theme_name=theme.theme_name,
                    is_primary=bool(mapping.is_primary),
                )
            )
        return MarketThemeByStockResponse(
            stock_code=(stock_code or "").strip(),
            stock_name=stock_name,
            themes=themes,
        )

    def list_stock_memos(self, stock_code: str) -> MarketThemeStockMemoResponse:
        normalized_code = normalize_stock_code(stock_code)
        if len(normalized_code) != 6:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid stock_code")
        stock = self.stock_repo.get_by_code(normalized_code)
        rows = self.db.execute(
            text(
                """
                SELECT trade_date AS memo_date,
                       TRIM(user_memo) AS memo,
                       COALESCE(detection_source, 'market_trend_event') AS source,
                       created_at,
                       updated_at
                FROM market_trend_events
                WHERE stock_code=:stock_code
                  AND TRIM(COALESCE(user_memo, '')) <> ''
                  AND COALESCE(is_active, 1) = 1
                  AND COALESCE(deleted_at, '') = ''
                ORDER BY trade_date DESC, updated_at DESC, id DESC
                LIMIT 100
                """
            ),
            {"stock_code": normalized_code},
        ).mappings().all()
        seen: set[tuple[str, str]] = set()
        items: list[MarketThemeStockMemoItem] = []
        for row in rows:
            memo_date = str(row["memo_date"] or "")[:10]
            memo = str(row["memo"] or "").strip()
            if not memo_date or not memo:
                continue
            key = (memo_date, memo)
            if key in seen:
                continue
            seen.add(key)
            items.append(
                MarketThemeStockMemoItem(
                    memo_date=memo_date,
                    memo=memo,
                    source=row["source"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
            )
        return MarketThemeStockMemoResponse(
            stock_code=normalized_code,
            stock_name=stock.stock_name if stock else None,
            items=items,
        )
