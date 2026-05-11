from __future__ import annotations

from sqlalchemy import Select, select, text
from sqlalchemy.orm import Session

from backend.app.core.config import now_kst
from backend.app.entities.stock_daily_price import StockDailyPrice


class StockPriceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert_daily_rows(self, stock_id: int, source: str, rows: list[dict]) -> int:
        if not rows:
            return 0
        sql = text(
            """
            INSERT INTO stock_daily_prices (
                stock_id, trade_date,
                open_price, high_price, low_price, close_price,
                change_price, change_rate, volume, trading_value,
                source, created_at, updated_at
            ) VALUES (
                :stock_id, :trade_date,
                :open_price, :high_price, :low_price, :close_price,
                :change_price, :change_rate, :volume, :trading_value,
                :source, :created_at, :updated_at
            )
            ON CONFLICT(stock_id, trade_date) DO UPDATE SET
                open_price=excluded.open_price,
                high_price=excluded.high_price,
                low_price=excluded.low_price,
                close_price=excluded.close_price,
                change_price=excluded.change_price,
                change_rate=excluded.change_rate,
                volume=excluded.volume,
                trading_value=excluded.trading_value,
                source=excluded.source,
                updated_at=excluded.updated_at
            """
        )
        now = now_kst()
        params = []
        for row in rows:
            params.append(
                {
                    "stock_id": stock_id,
                    "trade_date": row["trade_date"],
                    "open_price": row.get("open_price"),
                    "high_price": row.get("high_price"),
                    "low_price": row.get("low_price"),
                    "close_price": row.get("close_price"),
                    "change_price": row.get("change_price"),
                    "change_rate": row.get("change_rate"),
                    "volume": row.get("volume"),
                    "trading_value": row.get("trading_value"),
                    "source": source,
                    "created_at": now,
                    "updated_at": now,
                }
            )
        self.db.execute(sql, params)
        self.db.commit()
        return len(rows)

    def list_by_stock(self, stock_id: int, start_date: str | None, end_date: str | None, limit: int, offset: int) -> list[StockDailyPrice]:
        stmt: Select[tuple[StockDailyPrice]] = select(StockDailyPrice).where(StockDailyPrice.stock_id == stock_id)
        if start_date:
            stmt = stmt.where(StockDailyPrice.trade_date >= start_date)
        if end_date:
            stmt = stmt.where(StockDailyPrice.trade_date <= end_date)
        stmt = stmt.order_by(StockDailyPrice.trade_date.desc(), StockDailyPrice.id.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt).all())

    def list_by_stock_asc(self, stock_id: int) -> list[StockDailyPrice]:
        stmt: Select[tuple[StockDailyPrice]] = (
            select(StockDailyPrice)
            .where(StockDailyPrice.stock_id == stock_id)
            .order_by(StockDailyPrice.trade_date.asc(), StockDailyPrice.id.asc())
        )
        return list(self.db.scalars(stmt).all())

    def update_moving_averages(
        self,
        row_id: int,
        ma5: float | None,
        ma10: float | None,
        ma20: float | None,
        ma60: float | None,
        ma120: float | None,
        ma240: float | None,
    ) -> None:
        row = self.db.get(StockDailyPrice, row_id)
        if not row:
            return
        row.ma5 = ma5
        row.ma10 = ma10
        row.ma20 = ma20
        row.ma60 = ma60
        row.ma120 = ma120
        row.ma240 = ma240
        row.updated_at = now_kst()
        self.db.add(row)

    def commit(self) -> None:
        self.db.commit()
