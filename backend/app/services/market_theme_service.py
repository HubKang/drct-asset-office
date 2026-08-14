from __future__ import annotations

import json
import re

from fastapi import HTTPException, status
from sqlalchemy import bindparam, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.entities.market_theme import MarketTheme
from backend.app.repositories.market_theme_repository import MarketThemeRepository
from backend.app.schemas.market_theme_schema import (
    MarketThemeCreateRequest,
    MarketThemeDeleteResponse,
    MarketThemeResponse,
    MarketThemeUpdateRequest,
    THEME_LEVEL_GROUP,
    THEME_LEVEL_THEME,
)

ALLOWED_THEME_TYPES = {"industry", "theme", "custom", "telegram"}
ALLOWED_THEME_LEVELS = {THEME_LEVEL_GROUP, THEME_LEVEL_THEME}


class MarketThemeService:
    def __init__(self, db: Session) -> None:
        self.db = db
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

    def _latest_return_summary(self, theme_id: int) -> dict[str, object] | None:
        row = self.db.execute(
            text(
                """
                SELECT return_date, avg_change_rate, last_refreshed_at, stock_count,
                       success_stock_count, failed_stock_count, total_trading_value_100m
                FROM market_theme_daily_returns
                WHERE theme_id=:theme_id
                ORDER BY return_date DESC, last_refreshed_at DESC, id DESC
                LIMIT 1
                """
            ),
            {"theme_id": theme_id},
        ).mappings().first()
        return dict(row) if row else None

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
            latest_return=self._latest_return_summary(row.id) if theme_level == THEME_LEVEL_THEME else None,
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

    def delete_theme(self, theme_id: int) -> MarketThemeDeleteResponse:
        root = self.repo.get_by_id(theme_id)
        if not root:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="market theme not found")
        if root.is_active == 1:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="활성 테마는 삭제할 수 없습니다. 먼저 비활성화해 주세요.")

        descendants: list[MarketTheme] = [root]
        pending_parent_ids = [root.id]
        while pending_parent_ids:
            children = list(
                self.db.scalars(
                    select(MarketTheme).where(MarketTheme.parent_theme_id.in_(pending_parent_ids))
                ).all()
            )
            descendants.extend(children)
            pending_parent_ids = [child.id for child in children]

        active_children = [row.theme_name for row in descendants[1:] if row.is_active == 1]
        if active_children:
            names = ", ".join(active_children[:3])
            suffix = " 외" if len(active_children) > 3 else ""
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"활성 하위 테마가 있어 삭제할 수 없습니다: {names}{suffix}. 먼저 비활성화해 주세요.",
            )

        theme_ids = [row.id for row in descendants]
        theme_ids_param = bindparam("theme_ids", expanding=True)
        related_tables = (
            ("market_theme_stock_daily_returns", "theme_id"),
            ("market_theme_daily_returns", "theme_id"),
            ("market_theme_realtime_returns", "theme_id"),
            ("market_theme_return_prediction_items", "theme_id"),
            ("market_theme_observation_items", "theme_id"),
            ("market_theme_observation_validation_samples", "theme_id"),
            ("market_calendar_events", "theme_id"),
            ("daily_theme_flow_ranks", "market_theme_id"),
            ("briefing_theme_links", "market_theme_id"),
            ("market_trend_event_theme_links", "market_theme_id"),
            ("market_theme_stock_candidates", "theme_id"),
            ("market_theme_stocks", "theme_id"),
        )

        deleted_related_rows = 0
        detached_event_references = 0
        try:
            for column in ("theme_id", "primary_theme_id"):
                result = self.db.execute(
                    text(f"UPDATE market_trend_events SET {column}=NULL WHERE {column} IN :theme_ids")
                    .bindparams(theme_ids_param),
                    {"theme_ids": theme_ids},
                )
                detached_event_references += max(int(result.rowcount or 0), 0)

            mapping_result = self.db.execute(
                text(
                    "DELETE FROM market_index_theme_mappings "
                    "WHERE theme_id IN :theme_ids OR theme_group_id IN :theme_ids"
                ).bindparams(theme_ids_param),
                {"theme_ids": theme_ids},
            )
            deleted_related_rows += max(int(mapping_result.rowcount or 0), 0)

            for table_name, column_name in related_tables:
                result = self.db.execute(
                    text(f"DELETE FROM {table_name} WHERE {column_name} IN :theme_ids")
                    .bindparams(theme_ids_param),
                    {"theme_ids": theme_ids},
                )
                deleted_related_rows += max(int(result.rowcount or 0), 0)

            for row in reversed(descendants):
                self.db.delete(row)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="연결된 데이터 때문에 삭제할 수 없습니다. 관련 연결을 확인해 주세요.",
            ) from exc
        except Exception:
            self.db.rollback()
            raise

        return MarketThemeDeleteResponse(
            deleted_theme_id=root.id,
            deleted_theme_name=root.theme_name,
            deleted_theme_count=len(descendants),
            deleted_related_row_count=deleted_related_rows,
            detached_event_reference_count=detached_event_references,
        )
