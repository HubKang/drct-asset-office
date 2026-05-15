from __future__ import annotations

from sqlalchemy import Select, func, select, text
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.entities.stock_daily_market_metric import StockDailyMarketMetric


class StockMarketMetricRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert_rows(self, rows: list[dict]) -> int:
        if not rows:
            return 0

        sql = text(
            """
            INSERT INTO stock_daily_market_metrics (
                stock_id, trade_date, market, close_price, market_cap, listed_shares,
                trading_volume, trading_value, market_cap_rank, trading_value_rank,
                market_trading_value_rank, trading_value_percentile, market_trading_value_percentile,
                source, created_at, updated_at
            ) VALUES (
                :stock_id, :trade_date, :market, :close_price, :market_cap, :listed_shares,
                :trading_volume, :trading_value, :market_cap_rank, :trading_value_rank,
                :market_trading_value_rank, :trading_value_percentile, :market_trading_value_percentile,
                :source, :created_at, :updated_at
            )
            ON CONFLICT(stock_id, trade_date, source) DO UPDATE SET
                market=excluded.market,
                close_price=excluded.close_price,
                market_cap=excluded.market_cap,
                listed_shares=excluded.listed_shares,
                trading_volume=excluded.trading_volume,
                trading_value=excluded.trading_value,
                market_cap_rank=excluded.market_cap_rank,
                trading_value_rank=excluded.trading_value_rank,
                market_trading_value_rank=excluded.market_trading_value_rank,
                trading_value_percentile=excluded.trading_value_percentile,
                market_trading_value_percentile=excluded.market_trading_value_percentile,
                updated_at=excluded.updated_at
            """
        )
        now = now_kst()
        params = [{**row, "created_at": now, "updated_at": now} for row in rows]
        try:
            self.db.execute(sql, params)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return len(rows)

    def count_by_source(self, source: str) -> int:
        stmt = select(func.count(StockDailyMarketMetric.id)).where(StockDailyMarketMetric.source == source)
        return int(self.db.scalar(stmt) or 0)

    def get_latest_source_date(self, source: str) -> str | None:
        stmt = select(func.max(StockDailyMarketMetric.trade_date)).where(StockDailyMarketMetric.source == source)
        return self.db.scalar(stmt)

    def count_by_trade_date(self, trade_date: str, source: str) -> int:
        stmt = select(func.count(StockDailyMarketMetric.id)).where(
            StockDailyMarketMetric.trade_date == trade_date,
            StockDailyMarketMetric.source == source,
        )
        return int(self.db.scalar(stmt) or 0)

    def list_by_trade_date(self, trade_date: str, source: str, limit: int = 100) -> list[StockDailyMarketMetric]:
        stmt: Select[tuple[StockDailyMarketMetric]] = (
            select(StockDailyMarketMetric)
            .where(StockDailyMarketMetric.trade_date == trade_date, StockDailyMarketMetric.source == source)
            .order_by(StockDailyMarketMetric.trading_value_rank.asc(), StockDailyMarketMetric.stock_id.asc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def get_latest_by_stock_id(self, stock_id: int, source: str) -> StockDailyMarketMetric | None:
        stmt: Select[tuple[StockDailyMarketMetric]] = (
            select(StockDailyMarketMetric)
            .where(StockDailyMarketMetric.stock_id == stock_id, StockDailyMarketMetric.source == source)
            .order_by(StockDailyMarketMetric.trade_date.desc(), StockDailyMarketMetric.id.desc())
            .limit(1)
        )
        return self.db.scalars(stmt).first()
