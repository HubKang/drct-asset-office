from __future__ import annotations

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.entities.market_theme import MarketTheme
from backend.app.entities.market_theme_stock import MarketThemeStock
from backend.app.entities.stock import Stock
from backend.app.schemas.market_theme_stock_schema import (
    MarketThemeStockCreateRequest,
    MarketThemeStockMemoUpdateRequest,
)
from backend.app.services.market_theme_stock_service import MarketThemeStockService


def _seed() -> tuple[Session, MarketTheme, MarketTheme, Stock]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Stock.__table__.create(engine)
    MarketTheme.__table__.create(engine)
    MarketThemeStock.__table__.create(engine)
    db = Session(engine)
    now = "2026-08-08 10:00:00"
    stock = Stock(stock_code="033100", stock_name="제룡전기", market="KOSDAQ", is_active=1, created_at=now, updated_at=now)
    themes = [
        MarketTheme(theme_name=name, theme_code=code, theme_type="theme", theme_level="THEME", keywords="[]", is_supply_theme=0, is_active=1, sort_order=index, created_at=now, updated_at=now)
        for index, (name, code) in enumerate((("전력인프라", "POWER"), ("AI전력", "AI_POWER")), start=1)
    ]
    db.add_all([stock, *themes])
    db.commit()
    return db, themes[0], themes[1], stock


def test_memo_create_update_clear_and_theme_independence() -> None:
    db, theme_a, theme_b, stock = _seed()
    service = MarketThemeStockService(db)
    service.create_theme_stock(theme_a.id, MarketThemeStockCreateRequest(stock_id=stock.id))
    service.create_theme_stock(theme_b.id, MarketThemeStockCreateRequest(stock_id=stock.id))

    saved_a = service.update_theme_stock_memo(theme_a.id, stock.id, MarketThemeStockMemoUpdateRequest(stock_memo="  변압기  "))
    saved_b = service.update_theme_stock_memo(theme_b.id, stock.id, MarketThemeStockMemoUpdateRequest(stock_memo="AI 전력"))
    assert saved_a.stock_memo == "변압기"
    assert saved_b.stock_memo == "AI 전력"

    cleared = service.update_theme_stock_memo(theme_a.id, stock.id, MarketThemeStockMemoUpdateRequest(stock_memo="   "))
    assert cleared.stock_memo is None
    assert service.repo.get_by_theme_stock(theme_b.id, stock.id).stock_memo == "AI 전력"


def test_memo_survives_deactivate_and_reactivate() -> None:
    db, theme, _, stock = _seed()
    service = MarketThemeStockService(db)
    mapping = service.create_theme_stock(theme.id, MarketThemeStockCreateRequest(stock_id=stock.id))
    service.update_theme_stock_memo(theme.id, stock.id, MarketThemeStockMemoUpdateRequest(stock_memo="전력케이블"))
    service.deactivate_theme_stock(mapping.mapping_id)
    reactivated = service.create_theme_stock(theme.id, MarketThemeStockCreateRequest(stock_id=stock.id))
    assert reactivated.stock_memo == "전력케이블"


def test_missing_relation_and_length_validation() -> None:
    db, theme, _, stock = _seed()
    with pytest.raises(HTTPException) as exc_info:
        MarketThemeStockService(db).update_theme_stock_memo(theme.id, stock.id, MarketThemeStockMemoUpdateRequest(stock_memo="변압기"))
    assert exc_info.value.status_code == 404
    with pytest.raises(ValidationError):
        MarketThemeStockMemoUpdateRequest(stock_memo="가" * 101)
