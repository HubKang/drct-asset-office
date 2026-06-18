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
    THEME_LEVEL_GROUP,
    THEME_LEVEL_THEME,
)

ALLOWED_THEME_TYPES = {"industry", "theme", "custom", "telegram"}
ALLOWED_THEME_LEVELS = {THEME_LEVEL_GROUP, THEME_LEVEL_THEME}


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

    def _build_theme_stats(self) -> dict[int, dict[str, int | str | None]]:
        rows = self.repo.list_all_with_stock_count()
        theme_by_id = {theme.id: theme for theme, _ in rows}
        direct_stock_count = {theme.id: int(stock_count) for theme, stock_count in rows}
        direct_keyword_count = {
            theme.id: len(self.repo.parse_keywords(theme.keywords))
            for theme, _ in rows
        }
        stats: dict[int, dict[str, int | str | None]] = {}
        for theme, stock_count in rows:
            stats[theme.id] = {
                "parent_theme_name": theme_by_id.get(theme.parent_theme_id).theme_name if theme.parent_theme_id in theme_by_id else None,
                "linked_stock_count": int(stock_count),
                "keyword_count": direct_keyword_count.get(theme.id, 0),
                "child_theme_count": 0,
                "supply_child_theme_count": 0,
            }

        for theme, _ in rows:
            if theme.parent_theme_id is None:
                continue
            parent_stats = stats.get(theme.parent_theme_id)
            if not parent_stats:
                continue
            parent_stats["child_theme_count"] = int(parent_stats["child_theme_count"] or 0) + 1
            if theme.is_supply_theme == 1:
                parent_stats["supply_child_theme_count"] = int(parent_stats["supply_child_theme_count"] or 0) + 1
            parent_stats["keyword_count"] = int(parent_stats["keyword_count"] or 0) + direct_keyword_count.get(theme.id, 0)
            parent_stats["linked_stock_count"] = int(parent_stats["linked_stock_count"] or 0) + direct_stock_count.get(theme.id, 0)
        return stats

    def _to_response(
        self,
        row: MarketTheme,
        stock_count: int,
        stats: dict[int, dict[str, int | str | None]] | None = None,
    ) -> MarketThemeResponse:
        theme_level = (row.theme_level or THEME_LEVEL_THEME).strip() or THEME_LEVEL_THEME
        row_stats = stats.get(row.id, {}) if stats else {}
        keyword_count = int(row_stats.get("keyword_count") or len(self.repo.parse_keywords(row.keywords)))
        linked_stock_count = int(row_stats.get("linked_stock_count") or stock_count)
        return MarketThemeResponse(
            id=row.id,
            theme_name=row.theme_name,
            theme_code=row.theme_code,
            theme_type=row.theme_type,
            theme_level=theme_level,
            description=row.description,
            keywords=self.repo.parse_keywords(row.keywords),
            parent_theme_id=row.parent_theme_id,
            parent_theme_name=row_stats.get("parent_theme_name") if isinstance(row_stats.get("parent_theme_name"), str) else None,
            is_supply_theme=row.is_supply_theme,
            is_active=row.is_active,
            sort_order=row.sort_order,
            stock_count=linked_stock_count if theme_level == THEME_LEVEL_GROUP else stock_count,
            linked_stock_count=linked_stock_count,
            keyword_count=keyword_count,
            child_theme_count=int(row_stats.get("child_theme_count") or 0),
            supply_child_theme_count=int(row_stats.get("supply_child_theme_count") or 0),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _normalize_theme_level(self, value: str | None) -> str:
        normalized = (value or THEME_LEVEL_THEME).strip().upper()
        if normalized not in ALLOWED_THEME_LEVELS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid theme_level")
        return normalized

    def _validate_parent_theme(self, *, theme_level: str, parent_theme_id: int | None, current_theme_id: int | None = None) -> int | None:
        if theme_level == THEME_LEVEL_GROUP:
            return None
        if parent_theme_id is None:
            return None
        if current_theme_id is not None and parent_theme_id == current_theme_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="테마 자신을 상위 테마그룹으로 지정할 수 없습니다.")
        parent = self.repo.get_by_id(parent_theme_id)
        if not parent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="상위 테마그룹을 찾을 수 없습니다.")
        if (parent.theme_level or THEME_LEVEL_THEME) != THEME_LEVEL_GROUP:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="상위 항목은 테마그룹이어야 합니다.")
        return parent_theme_id

    def list_themes(
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
    ) -> list[MarketThemeResponse]:
        normalized_level = self._normalize_theme_level(theme_level) if theme_level else None
        rows = self.repo.list_with_stock_count(
            is_active=is_active,
            theme_type=theme_type,
            theme_level=normalized_level,
            parent_theme_id=parent_theme_id,
            is_supply_theme=is_supply_theme,
            keyword=keyword,
            limit=limit,
            offset=offset,
        )
        stats = self._build_theme_stats()
        return [self._to_response(theme, int(stock_count), stats) for theme, stock_count in rows]

    def get_theme(self, theme_id: int) -> MarketThemeResponse:
        row = self.repo.get_with_stock_count(theme_id)
        if row:
            theme, stock_count = row
            return self._to_response(theme, stock_count, self._build_theme_stats())
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="market theme not found")

    def create_theme(self, payload: MarketThemeCreateRequest) -> MarketThemeResponse:
        if payload.theme_type not in ALLOWED_THEME_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid theme_type")

        keywords = self._normalize_keywords(payload.keywords)
        theme_level = self._normalize_theme_level(payload.theme_level)
        parent_theme_id = self._validate_parent_theme(theme_level=theme_level, parent_theme_id=payload.parent_theme_id)
        theme_code = self._generate_theme_code(payload.theme_name, payload.theme_code)
        now = now_kst()
        row = MarketTheme(
            theme_name=payload.theme_name.strip(),
            theme_code=theme_code,
            theme_type=payload.theme_type.strip(),
            theme_level=theme_level,
            description=payload.description,
            keywords=json.dumps(keywords, ensure_ascii=False),
            parent_theme_id=parent_theme_id,
            is_supply_theme=1 if payload.is_supply_theme else 0,
            is_active=1 if payload.is_active else 0,
            sort_order=payload.sort_order,
            created_at=now,
            updated_at=now,
        )
        created = self.repo.create(row)
        return self._to_response(created, stock_count=0, stats=self._build_theme_stats())

    def update_theme(self, theme_id: int, payload: MarketThemeUpdateRequest) -> MarketThemeResponse:
        if payload.theme_type not in ALLOWED_THEME_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid theme_type")

        row = self.repo.get_by_id(theme_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="market theme not found")

        keywords = self._normalize_keywords(payload.keywords)
        theme_level = self._normalize_theme_level(payload.theme_level)
        parent_theme_id = self._validate_parent_theme(
            theme_level=theme_level,
            parent_theme_id=payload.parent_theme_id,
            current_theme_id=theme_id,
        )
        row.theme_name = payload.theme_name.strip()
        row.theme_type = payload.theme_type.strip()
        row.theme_level = theme_level
        row.description = payload.description
        row.keywords = json.dumps(keywords, ensure_ascii=False)
        row.parent_theme_id = parent_theme_id
        row.is_supply_theme = 1 if payload.is_supply_theme else 0
        row.is_active = 1 if payload.is_active else 0
        row.sort_order = payload.sort_order
        row.updated_at = now_kst()
        updated = self.repo.update(row)
        stock_count = self.repo.get_stock_count(theme_id)
        return self._to_response(updated, stock_count=stock_count, stats=self._build_theme_stats())

    def deactivate_theme(self, theme_id: int) -> MarketThemeResponse:
        row = self.repo.get_by_id(theme_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="market theme not found")
        row.is_active = 0
        row.updated_at = now_kst()
        updated = self.repo.update(row)
        return self._to_response(updated, stock_count=self.repo.get_stock_count(theme_id), stats=self._build_theme_stats())
