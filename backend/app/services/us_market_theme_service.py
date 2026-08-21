from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.entities.us_market_theme import UsTheme, UsThemeGroup, UsThemeStock
from backend.app.repositories.us_market_theme_repository import UsMarketThemeRepository
from backend.app.repositories.us_stock_repository import UsStockRepository
from backend.app.schemas.us_market_theme_schema import (
    UsThemeGroupInput,
    UsThemeGroupResponse,
    UsThemeGroupUpdate,
    UsThemeInput,
    UsThemeResponse,
    UsThemeStockInput,
    UsThemeStockResponse,
    UsThemeStockUpdate,
    UsThemeSummaryResponse,
    UsThemeUpdate,
)


def _keywords_to_db(values: list[str]) -> str:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = value.strip()
        key = item.casefold()
        if item and key not in seen:
            cleaned.append(item)
            seen.add(key)
    return "\n".join(cleaned)


def _keywords_from_db(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").splitlines() if item.strip()]


class UsMarketThemeService:
    def __init__(self, db: Session) -> None:
        self.repo = UsMarketThemeRepository(db)
        self.stock_repo = UsStockRepository(db)

    def _group_response(self, row: tuple[UsThemeGroup, int, int, int]) -> UsThemeGroupResponse:
        group, total, active, linked = row
        return UsThemeGroupResponse(id=group.id, name=group.name, description=group.description, sort_order=group.sort_order, active=group.active, theme_count=total, active_theme_count=active, linked_stock_count=linked, created_at=group.created_at, updated_at=group.updated_at)

    def _theme_response(self, row: tuple[UsTheme, str, int, str | None], latest: dict[str, object] | None = None) -> UsThemeResponse:
        theme, group_name, linked, representatives = row
        return UsThemeResponse(id=theme.id, theme_group_id=theme.theme_group_id, theme_group_name=group_name, name=theme.name, description=theme.description, keywords=_keywords_from_db(theme.keywords), sort_order=theme.sort_order, active=theme.active, linked_stock_count=linked, representative_symbols=[value for value in (representatives or "").split(",") if value], created_at=theme.created_at, updated_at=theme.updated_at, latest_return_date=str(latest["trade_date"]) if latest else None, latest_simple_return=float(latest["simple_return"]) if latest else None, latest_theme_strength=float(latest["theme_strength"]) if latest else None, latest_breadth_ratio=float(latest["breadth_ratio"]) if latest else None)

    @staticmethod
    def _mapping_response(mapping: UsThemeStock, stock) -> UsThemeStockResponse:
        return UsThemeStockResponse(mapping_id=mapping.id, theme_id=mapping.theme_id, us_stock_id=mapping.us_stock_id, symbol=stock.symbol, name=stock.name, name_ko=stock.name_ko, exchange=stock.exchange, stock_type=stock.stock_type, naver_code=stock.naver_code, role=mapping.role, is_representative=mapping.is_representative, sort_order=mapping.sort_order, active=mapping.active, created_at=mapping.created_at, updated_at=mapping.updated_at)

    def summary(self) -> UsThemeSummaryResponse:
        return UsThemeSummaryResponse(**self.repo.summary())

    def list_groups(self) -> list[UsThemeGroupResponse]:
        return [self._group_response(row) for row in self.repo.list_groups()]

    def create_group(self, payload: UsThemeGroupInput) -> UsThemeGroupResponse:
        now = now_kst()
        try:
            saved = self.repo.save(UsThemeGroup(**payload.model_dump(), created_at=now, updated_at=now))
        except IntegrityError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="같은 이름의 미국 테마그룹이 이미 있습니다.") from exc
        return next(row for row in self.list_groups() if row.id == saved.id)

    def update_group(self, group_id: int, payload: UsThemeGroupUpdate) -> UsThemeGroupResponse:
        group = self.repo.get_group(group_id)
        if not group:
            raise HTTPException(status_code=404, detail="미국 테마그룹을 찾을 수 없습니다.")
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(group, key, value)
        group.updated_at = now_kst()
        try:
            self.repo.save(group)
        except IntegrityError as exc:
            raise HTTPException(status_code=409, detail="같은 이름의 미국 테마그룹이 이미 있습니다.") from exc
        return next(row for row in self.list_groups() if row.id == group.id)

    def list_themes(self, *, group_id: int | None, active: int | None, keyword: str | None) -> list[UsThemeResponse]:
        rows = self.repo.list_themes(group_id=group_id, active=active, keyword=keyword)
        latest = self.repo.latest_returns([row[0].id for row in rows])
        return [self._theme_response(row, latest.get(row[0].id)) for row in rows]

    def create_theme(self, payload: UsThemeInput) -> UsThemeResponse:
        if not self.repo.get_group(payload.theme_group_id):
            raise HTTPException(status_code=404, detail="미국 테마그룹을 찾을 수 없습니다.")
        now = now_kst()
        data = payload.model_dump(exclude={"keywords"})
        try:
            saved = self.repo.save(UsTheme(**data, keywords=_keywords_to_db(payload.keywords), created_at=now, updated_at=now))
        except IntegrityError as exc:
            raise HTTPException(status_code=409, detail="해당 그룹에 같은 이름의 미국 테마가 이미 있습니다.") from exc
        return next(row for row in self.list_themes(group_id=None, active=None, keyword=None) if row.id == saved.id)

    def update_theme(self, theme_id: int, payload: UsThemeUpdate) -> UsThemeResponse:
        theme = self.repo.get_theme(theme_id)
        if not theme:
            raise HTTPException(status_code=404, detail="미국 테마를 찾을 수 없습니다.")
        data = payload.model_dump(exclude_unset=True)
        if data.get("theme_group_id") is not None and not self.repo.get_group(data["theme_group_id"]):
            raise HTTPException(status_code=404, detail="미국 테마그룹을 찾을 수 없습니다.")
        if "keywords" in data:
            data["keywords"] = _keywords_to_db(data["keywords"] or [])
        for key, value in data.items():
            setattr(theme, key, value)
        theme.updated_at = now_kst()
        try:
            self.repo.save(theme)
        except IntegrityError as exc:
            raise HTTPException(status_code=409, detail="해당 그룹에 같은 이름의 미국 테마가 이미 있습니다.") from exc
        return next(row for row in self.list_themes(group_id=None, active=None, keyword=None) if row.id == theme.id)

    def list_theme_stocks(self, theme_id: int) -> list[UsThemeStockResponse]:
        if not self.repo.get_theme(theme_id):
            raise HTTPException(status_code=404, detail="미국 테마를 찾을 수 없습니다.")
        return [self._mapping_response(mapping, stock) for mapping, stock in self.repo.list_theme_stocks(theme_id)]

    def link_stock(self, theme_id: int, payload: UsThemeStockInput) -> UsThemeStockResponse:
        if not self.repo.get_theme(theme_id):
            raise HTTPException(status_code=404, detail="미국 테마를 찾을 수 없습니다.")
        stock = self.stock_repo.get_by_id(payload.us_stock_id)
        if not stock:
            raise HTTPException(status_code=404, detail="미국 종목을 찾을 수 없습니다.")
        existing = self.repo.get_mapping_by_pair(theme_id, payload.us_stock_id)
        now = now_kst()
        if existing:
            if existing.active == 1:
                raise HTTPException(status_code=409, detail="이미 연결된 미국 종목입니다.")
            existing.role = payload.role
            existing.is_representative = payload.is_representative
            existing.sort_order = payload.sort_order
            existing.active = 1
            existing.updated_at = now
            mapping = self.repo.save(existing)
        else:
            mapping = self.repo.save(UsThemeStock(theme_id=theme_id, **payload.model_dump(), active=1, created_at=now, updated_at=now))
        return self._mapping_response(mapping, stock)

    def update_mapping(self, mapping_id: int, payload: UsThemeStockUpdate) -> UsThemeStockResponse:
        mapping = self.repo.get_mapping(mapping_id)
        if not mapping:
            raise HTTPException(status_code=404, detail="미국 테마 종목 연결을 찾을 수 없습니다.")
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(mapping, key, value)
        mapping.updated_at = now_kst()
        self.repo.save(mapping)
        stock = self.stock_repo.get_by_id(mapping.us_stock_id)
        return self._mapping_response(mapping, stock)

    def unlink_mapping(self, mapping_id: int) -> UsThemeStockResponse:
        return self.update_mapping(mapping_id, UsThemeStockUpdate(active=0))
