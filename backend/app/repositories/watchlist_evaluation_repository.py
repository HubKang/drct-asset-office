from __future__ import annotations

from typing import Any

from sqlalchemy import Select, func, select, text
from sqlalchemy.orm import Session

from backend.app.entities.stock import Stock
from backend.app.entities.stock_daily_market_metric import StockDailyMarketMetric
from backend.app.entities.stock_daily_price import StockDailyPrice
from backend.app.entities.watchlist import Watchlist
from backend.app.entities.watchlist_evaluation import (
    WatchlistEvaluationFactor,
    WatchlistEvaluationRun,
    WatchlistEvaluationScore,
)


class WatchlistEvaluationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_watchlist_with_latest_scores(
        self,
    ) -> list[tuple[Watchlist, Stock, WatchlistEvaluationScore | None, int | None, int | None]]:
        latest_score_subq = (
            select(
                WatchlistEvaluationScore.watchlist_stock_id.label("watchlist_stock_id"),
                func.max(WatchlistEvaluationScore.id).label("score_id"),
            )
            .group_by(WatchlistEvaluationScore.watchlist_stock_id)
            .subquery()
        )
        price_count_subq = (
            select(StockDailyPrice.stock_id.label("stock_id"), func.count(StockDailyPrice.id).label("price_count"))
            .group_by(StockDailyPrice.stock_id)
            .subquery()
        )
        metrics_count_subq = (
            select(
                StockDailyMarketMetric.stock_id.label("stock_id"),
                func.count(StockDailyMarketMetric.id).label("metrics_count"),
            )
            .group_by(StockDailyMarketMetric.stock_id)
            .subquery()
        )
        stmt: Select[tuple[Watchlist, Stock, WatchlistEvaluationScore | None, int | None, int | None]] = (
            select(
                Watchlist,
                Stock,
                WatchlistEvaluationScore,
                price_count_subq.c.price_count,
                metrics_count_subq.c.metrics_count,
            )
            .join(Stock, Watchlist.stock_id == Stock.id)
            .outerjoin(latest_score_subq, latest_score_subq.c.watchlist_stock_id == Watchlist.id)
            .outerjoin(WatchlistEvaluationScore, WatchlistEvaluationScore.id == latest_score_subq.c.score_id)
            .outerjoin(price_count_subq, price_count_subq.c.stock_id == Stock.id)
            .outerjoin(metrics_count_subq, metrics_count_subq.c.stock_id == Stock.id)
            .order_by(Watchlist.is_active.desc(), Watchlist.registered_at.desc(), Watchlist.id.desc())
        )
        return list(self.db.execute(stmt).all())

    def list_watchlist_by_ids(self, watchlist_ids: list[int]) -> list[Watchlist]:
        if not watchlist_ids:
            return []
        stmt = select(Watchlist).where(Watchlist.id.in_(watchlist_ids)).order_by(Watchlist.id.asc())
        return list(self.db.scalars(stmt).all())

    def list_all_watchlist(self, include_inactive: bool) -> list[Watchlist]:
        stmt = select(Watchlist).order_by(Watchlist.id.asc())
        if not include_inactive:
            stmt = stmt.where(Watchlist.is_active == 1)
        return list(self.db.scalars(stmt).all())

    def create_run(self, run: WatchlistEvaluationRun) -> WatchlistEvaluationRun:
        self.db.add(run)
        self.db.flush()
        return run

    def create_score(self, score: WatchlistEvaluationScore) -> WatchlistEvaluationScore:
        self.db.add(score)
        self.db.flush()
        return score

    def create_factor(self, factor: WatchlistEvaluationFactor) -> WatchlistEvaluationFactor:
        self.db.add(factor)
        self.db.flush()
        return factor

    def get_score(self, score_id: int) -> WatchlistEvaluationScore | None:
        return self.db.get(WatchlistEvaluationScore, score_id)

    def list_factors(self, score_id: int) -> list[WatchlistEvaluationFactor]:
        stmt = select(WatchlistEvaluationFactor).where(WatchlistEvaluationFactor.score_id == score_id).order_by(
            WatchlistEvaluationFactor.id.asc()
        )
        return list(self.db.scalars(stmt).all())

    def list_latest_factors_by_watchlist_ids(self, watchlist_ids: list[int]) -> dict[int, list[WatchlistEvaluationFactor]]:
        if not watchlist_ids:
            return {}
        latest_score_subq = (
            select(
                WatchlistEvaluationScore.watchlist_stock_id.label("watchlist_stock_id"),
                func.max(WatchlistEvaluationScore.id).label("score_id"),
            )
            .where(WatchlistEvaluationScore.watchlist_stock_id.in_(watchlist_ids))
            .group_by(WatchlistEvaluationScore.watchlist_stock_id)
            .subquery()
        )
        stmt = (
            select(latest_score_subq.c.watchlist_stock_id, WatchlistEvaluationFactor)
            .join(WatchlistEvaluationFactor, WatchlistEvaluationFactor.score_id == latest_score_subq.c.score_id)
            .order_by(latest_score_subq.c.watchlist_stock_id.asc(), WatchlistEvaluationFactor.id.asc())
        )
        result: dict[int, list[WatchlistEvaluationFactor]] = {}
        for watchlist_id, factor in self.db.execute(stmt).all():
            result.setdefault(int(watchlist_id), []).append(factor)
        return result

    def list_history(self, watchlist_id: int) -> list[tuple[WatchlistEvaluationScore, WatchlistEvaluationRun]]:
        stmt = (
            select(WatchlistEvaluationScore, WatchlistEvaluationRun)
            .join(WatchlistEvaluationRun, WatchlistEvaluationRun.id == WatchlistEvaluationScore.run_id)
            .where(WatchlistEvaluationScore.watchlist_stock_id == watchlist_id)
            .order_by(WatchlistEvaluationScore.evaluated_at.desc(), WatchlistEvaluationScore.id.desc())
        )
        return list(self.db.execute(stmt).all())

    def list_market_index_daily_rows(self, index_code: str, limit: int = 80) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT index_code, price_date, close_price, change_rate, trading_value, ma20, ma60
                FROM market_index_daily_prices
                WHERE UPPER(index_code) = :index_code
                  AND close_price IS NOT NULL
                ORDER BY price_date DESC
                LIMIT :limit
                """
            ),
            {"index_code": index_code.strip().upper(), "limit": limit},
        ).mappings().all()
        return [dict(row) for row in reversed(rows)]

    def list_market_indicator_values(self, indicator_code: str, limit: int = 30) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT indicator_code, value_date, value, change_value, change_pct
                FROM market_indicator_values
                WHERE UPPER(indicator_code) = :indicator_code
                  AND value IS NOT NULL
                ORDER BY value_date DESC
                LIMIT :limit
                """
            ),
            {"indicator_code": indicator_code.strip().upper(), "limit": limit},
        ).mappings().all()
        return [dict(row) for row in reversed(rows)]

    def get_market_indicator_latest(self, indicator_code: str) -> dict[str, Any] | None:
        row = self.db.execute(
            text(
                """
                SELECT indicator_code, latest_value, latest_value_date, latest_change_value, latest_change_pct
                FROM market_indicators
                WHERE UPPER(indicator_code) = :indicator_code
                """
            ),
            {"indicator_code": indicator_code.strip().upper()},
        ).mappings().first()
        return dict(row) if row else None

    def list_stock_daily_price_rows(self, stock_id: int, limit: int = 80) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT stock_id, trade_date, open_price, high_price, low_price, close_price, change_rate, volume, trading_value
                FROM stock_daily_prices
                WHERE stock_id = :stock_id
                  AND close_price IS NOT NULL
                ORDER BY trade_date DESC
                LIMIT :limit
                """
            ),
            {"stock_id": stock_id, "limit": limit},
        ).mappings().all()
        return [dict(row) for row in reversed(rows)]

    def list_stock_themes(self, stock_id: int) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT
                    t.id AS theme_id,
                    t.theme_name,
                    t.theme_level,
                    t.parent_theme_id,
                    mts.is_primary
                FROM market_theme_stocks mts
                JOIN market_themes t ON t.id = mts.theme_id
                WHERE mts.stock_id = :stock_id
                  AND mts.is_active = 1
                  AND t.is_active = 1
                ORDER BY mts.is_primary DESC, t.sort_order ASC, t.theme_name ASC
                """
            ),
            {"stock_id": stock_id},
        ).mappings().all()
        return [dict(row) for row in rows]

    def list_theme_stocks(self, theme_id: int) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT mts.stock_id, s.stock_code, s.stock_name, mts.is_primary
                FROM market_theme_stocks mts
                JOIN stocks s ON s.id = mts.stock_id
                WHERE mts.theme_id = :theme_id
                  AND mts.is_active = 1
                ORDER BY mts.is_primary DESC, s.stock_name ASC
                """
            ),
            {"theme_id": theme_id},
        ).mappings().all()
        return [dict(row) for row in rows]


    def list_material_news(self, stock_id: int, limit: int = 30) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT
                    id,
                    stock_id,
                    title,
                    source,
                    url,
                    published_at,
                    collected_at,
                    summary,
                    sentiment,
                    importance_score,
                    ai_summary,
                    ai_sentiment,
                    ai_importance_score,
                    ai_tags,
                    ai_processed_at
                FROM news_items
                WHERE stock_id = :stock_id
                ORDER BY COALESCE(published_at, collected_at, created_at) DESC, id DESC
                LIMIT :limit
                """
            ),
            {"stock_id": stock_id, "limit": limit},
        ).mappings().all()
        return [dict(row) for row in rows]

    def list_material_disclosures(self, stock_id: int, limit: int = 30) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT
                    id,
                    stock_id,
                    dart_receipt_no,
                    disclosure_title,
                    disclosure_type,
                    disclosed_at,
                    url,
                    summary,
                    importance_score,
                    ai_summary,
                    ai_importance_score,
                    ai_tags,
                    ai_risk_level,
                    ai_event_type,
                    ai_processed_at,
                    created_at
                FROM disclosures
                WHERE stock_id = :stock_id
                ORDER BY COALESCE(disclosed_at, created_at) DESC, id DESC
                LIMIT :limit
                """
            ),
            {"stock_id": stock_id, "limit": limit},
        ).mappings().all()
        return [dict(row) for row in rows]

    def commit(self) -> None:
        self.db.commit()
