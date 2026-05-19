from __future__ import annotations

import json

from sqlalchemy import Select, and_, case, func, select
from sqlalchemy.orm import Session

from backend.app.entities.market_theme import MarketTheme
from backend.app.entities.market_theme_stock_candidate import MarketThemeStockCandidate
from backend.app.entities.stock import Stock


class MarketThemeCandidateRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, candidate_id: int) -> MarketThemeStockCandidate | None:
        return self.db.get(MarketThemeStockCandidate, candidate_id)

    def get_by_unique(self, theme_id: int, stock_id: int, candidate_source: str) -> MarketThemeStockCandidate | None:
        stmt = select(MarketThemeStockCandidate).where(
            MarketThemeStockCandidate.theme_id == theme_id,
            MarketThemeStockCandidate.stock_id == stock_id,
            MarketThemeStockCandidate.candidate_source == candidate_source,
        )
        return self.db.scalar(stmt)

    def create(self, row: MarketThemeStockCandidate) -> MarketThemeStockCandidate:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def update(self, row: MarketThemeStockCandidate) -> MarketThemeStockCandidate:
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_candidates(
        self,
        *,
        status: str | None,
        theme_id: int | None,
        stock_id: int | None,
        candidate_source: str | None,
        limit: int,
        offset: int,
    ) -> list[tuple[MarketThemeStockCandidate, MarketTheme, Stock]]:
        pending_priority = case((MarketThemeStockCandidate.status == "pending", 0), else_=1)
        stmt: Select[tuple[MarketThemeStockCandidate, MarketTheme, Stock]] = (
            select(MarketThemeStockCandidate, MarketTheme, Stock)
            .join(MarketTheme, MarketTheme.id == MarketThemeStockCandidate.theme_id)
            .join(Stock, Stock.id == MarketThemeStockCandidate.stock_id)
            .order_by(
                pending_priority.asc(),
                MarketThemeStockCandidate.confidence_score.desc().nullslast(),
                MarketThemeStockCandidate.updated_at.desc(),
            )
        )
        if status:
            stmt = stmt.where(MarketThemeStockCandidate.status == status)
        if theme_id is not None:
            stmt = stmt.where(MarketThemeStockCandidate.theme_id == theme_id)
        if stock_id is not None:
            stmt = stmt.where(MarketThemeStockCandidate.stock_id == stock_id)
        if candidate_source:
            stmt = stmt.where(MarketThemeStockCandidate.candidate_source == candidate_source)
        stmt = stmt.limit(limit).offset(offset)
        return list(self.db.execute(stmt).all())

    @staticmethod
    def parse_keywords(raw: str | None) -> list[str]:
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if isinstance(data, list):
            return [str(x).strip() for x in data if str(x).strip()]
        return []

