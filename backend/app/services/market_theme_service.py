from __future__ import annotations

import json
import re

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.entities.market_theme import MarketTheme
from backend.app.repositories.market_theme_repository import MarketThemeRepository
from backend.app.schemas.market_theme_schema import (
    MarketThemeCreateRequest,
    MarketThemeResponse,
    MarketThemeUpdateRequest,
)

ALLOWED_THEME_TYPES = {"industry", "theme", "custom", "telegram"}


class MarketThemeService:
    def __init__(self, db: Session) -> None:
        self.repo = MarketThemeRepository(db)

    @staticmethod
    def _normalize_keywords(keywords: list[str]) -> list[str]:
        normalized = [item.strip() for item in keywords if item and item.strip()]
        return list(dict.fromkeys(normalized))

    def _generate_theme_code(self, theme_name: str, requested_code: str | None = None) -> str:
        base_raw = (requested_code or "").strip() or theme_name.strip()
        base = re.sub(r"[^a-z0-9]+", "-", base_raw.lower()).strip("-")
        if not base:
            base = "theme"
        candidate = base
        suffix = 1
        while self.repo.get_by_theme_code(candidate):
            suffix += 1
            candidate = f"{base}-{suffix}"
        return candidate

    def _to_response(self, row: MarketTheme, stock_count: int) -> MarketThemeResponse:
        return MarketThemeResponse(
            id=row.id,
            theme_name=row.theme_name,
            theme_code=row.theme_code,
            theme_type=row.theme_type,
            description=row.description,
            keywords=self.repo.parse_keywords(row.keywords),
            parent_theme_id=row.parent_theme_id,
            is_supply_theme=row.is_supply_theme,
            is_active=row.is_active,
            sort_order=row.sort_order,
            stock_count=stock_count,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def list_themes(
        self,
        *,
        is_active: int | None,
        theme_type: str | None,
        keyword: str | None,
        limit: int,
        offset: int,
    ) -> list[MarketThemeResponse]:
        rows = self.repo.list_with_stock_count(
            is_active=is_active,
            theme_type=theme_type,
            keyword=keyword,
            limit=limit,
            offset=offset,
        )
        return [self._to_response(theme, int(stock_count)) for theme, stock_count in rows]

    def get_theme(self, theme_id: int) -> MarketThemeResponse:
        row = self.repo.get_with_stock_count(theme_id)
        if row:
            theme, stock_count = row
            return self._to_response(theme, stock_count)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="market theme not found")

    def create_theme(self, payload: MarketThemeCreateRequest) -> MarketThemeResponse:
        if payload.theme_type not in ALLOWED_THEME_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid theme_type")

        keywords = self._normalize_keywords(payload.keywords)
        theme_code = self._generate_theme_code(payload.theme_name, payload.theme_code)
        now = now_kst()
        row = MarketTheme(
            theme_name=payload.theme_name.strip(),
            theme_code=theme_code,
            theme_type=payload.theme_type.strip(),
            description=payload.description,
            keywords=json.dumps(keywords, ensure_ascii=False),
            parent_theme_id=payload.parent_theme_id,
            is_supply_theme=1 if payload.is_supply_theme else 0,
            is_active=1 if payload.is_active else 0,
            sort_order=payload.sort_order,
            created_at=now,
            updated_at=now,
        )
        created = self.repo.create(row)
        return self._to_response(created, stock_count=0)

    def update_theme(self, theme_id: int, payload: MarketThemeUpdateRequest) -> MarketThemeResponse:
        if payload.theme_type not in ALLOWED_THEME_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid theme_type")

        row = self.repo.get_by_id(theme_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="market theme not found")

        keywords = self._normalize_keywords(payload.keywords)
        row.theme_name = payload.theme_name.strip()
        row.theme_type = payload.theme_type.strip()
        row.description = payload.description
        row.keywords = json.dumps(keywords, ensure_ascii=False)
        row.parent_theme_id = payload.parent_theme_id
        row.is_supply_theme = 1 if payload.is_supply_theme else 0
        row.is_active = 1 if payload.is_active else 0
        row.sort_order = payload.sort_order
        row.updated_at = now_kst()
        updated = self.repo.update(row)
        stock_count = self.repo.get_stock_count(theme_id)
        return self._to_response(updated, stock_count=stock_count)

    def deactivate_theme(self, theme_id: int) -> MarketThemeResponse:
        row = self.repo.get_by_id(theme_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="market theme not found")
        row.is_active = 0
        row.updated_at = now_kst()
        updated = self.repo.update(row)
        return self._to_response(updated, stock_count=self.repo.get_stock_count(theme_id))
